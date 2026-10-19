"""字型複本只留本機；重開時核對內容再載入程式，從不安裝系統字型。"""
from __future__ import annotations

import os
import re
from pathlib import Path
import shutil
import tempfile
import time
import uuid

from PySide6.QtGui import QFontDatabase

from .background import file_digest


def font_errors(asset: dict | None, family: str) -> list[str]:
    if asset is None:
        return []
    try:
        if not isinstance(asset, dict) or not isinstance(asset.get("families"), list) or not asset["families"]:
            return ["本機字型資產記錄不完整，需重新匯入"]
        if not isinstance(asset.get("hash"), str) or not re.fullmatch(r"[0-9a-f]{64}", asset["hash"]):
            return ["本機字型資產內容識別不合法，需重新匯入"]
        if asset.get("approved") is not True or family not in asset["families"]:
            return ["本機字型資產尚未核准或字型家族不符"]
        path = Path(asset["path"])
        if path.is_symlink():
            return ["本機字型資產位置含符號連結，需修復為正常複本"]
        if not path.is_file():
            return ["本機字型資產失聯，需重新匯入"]
        if path.stat().st_size > 50_000_000:
            return ["本機字型資產超出原支援大小，需重新匯入"]
        if file_digest(path) != asset["hash"]:
            return ["本機字型資產內容已變更，不沿用原核准"]
    except (KeyError, TypeError, AttributeError, OSError):
        return ["本機字型資產記錄不完整，需重新匯入"]
    return []


def font_asset_errors(slots) -> list[str]:
    errors = []
    seen = set()
    for slot in slots:
        for part in (slot.text_flow or {}).get('rich_text',{}).get('segments',[]):
            extra=part.get('font_asset')
            family=(extra.get('families') or [''])[0] if isinstance(extra,dict) else ''
            errors.extend('複合文字：'+error for error in font_errors(extra,family))
        asset = slot.font_asset
        if asset is None:
            continue
        key = (str(asset.get("hash")), str(asset.get("path")), slot.font, slot.font_style) if isinstance(asset, dict) else (id(asset), slot.font)
        if key not in seen:
            seen.add(key)
            errors.extend(slot.font + "：" + error for error in font_errors(asset, slot.font))
            if slot.font_style and not font_errors(asset,slot.font):
                from .font_catalog import raw_asset
                try:
                    if raw_asset(asset).styleName()!=slot.font_style:
                        errors.append(slot.font+"：款式與核准字面不同，不能借用同家族其他款式")
                except ValueError as error: errors.append(str(error))
    return errors


class FontManager:
    def __init__(self, library, lazy=False):
        self.library = library
        self.loaded = {}
        self.issues = []
        if not lazy:self._recover_repairs()
        for asset in ([] if lazy else library.fonts()):
            families = asset.get("families", []) if isinstance(asset, dict) else []
            family = families[0] if isinstance(families, list) and families else ""
            errors = font_errors(asset, family)
            if errors:
                self.issues.extend(errors)
                continue
            font_id = QFontDatabase.addApplicationFont(asset["path"])
            if font_id < 0:
                self.issues.append("已保存字型無法載入：" + asset.get("original_name", "未知"))
            else:
                self.loaded[asset["hash"]] = (font_id, asset)

    def ensure_slots(self,slots):
        assets=[]
        for slot in slots:
            assets.append(slot.font_asset)
            assets.extend(part.get('font_asset') for part in (slot.text_flow or {}).get('rich_text',{}).get('segments',[]))
        for asset in assets:
            if not asset:continue
            if not isinstance(asset,dict):self.issues.append('選中字型資產記錄不完整');continue
            if asset.get('hash') in self.loaded:continue
            errors=font_errors(asset,(asset.get('families') or [''])[0])
            if errors:self.issues.extend(errors);continue
            font_id=QFontDatabase.addApplicationFont(asset['path'])
            if font_id<0:self.issues.append('選中字型無法載入：'+(asset.get('families') or [''])[0])
            else:self.loaded[asset['hash']]=(font_id,asset)

    def asset_for_family(self, family: str) -> dict | None:
        # 失聯也保留引用，讓指定此資產的欄位阻擋，而不是偷偷借用同名系統字型。
        import json
        row=self.library.db.execute("SELECT payload FROM font_assets WHERE EXISTS(SELECT 1 FROM json_each(font_assets.payload,'$.families') WHERE value=?) ORDER BY rowid LIMIT 1",(family,)).fetchone()
        return json.loads(row[0]) if row else None

    def record_output_rights(self, expected, actor, basis, pdf_embedding=False):
        """Explicit attestation changes the asset record, never old templates."""
        from copy import deepcopy
        from .font_evidence import inspect_font
        if not isinstance(actor,str) or not actor.strip() or len(actor)>200 or not isinstance(basis,str) or not basis.strip() or len(basis)>2048 or type(pdf_embedding) is not bool:
            raise ValueError('授權需要核准者、依據及明確PDF用途')
        errors=font_errors(expected,expected['families'][0])
        if errors:raise ValueError('；'.join(errors))
        evidence=inspect_font(expected['path'])
        if len(evidence['faces'])!=1 or evidence['hash']!=expected['hash']:
            raise ValueError('字面身份不完整，請重新匯入明確字面')
        updated=deepcopy(expected)
        updated['font_evidence']=dict(evidence['faces'][0],source_hash=expected.get('font_evidence',{}).get('source_hash',evidence['hash']))
        updated['usage_rights']=dict(actor=actor.strip(),basis=basis.strip(),print_export=True,pdf_embedding=pdf_embedding)
        import json
        with self.library.db:
            row=self.library.db.execute('SELECT payload FROM font_assets WHERE hash=?',(expected['hash'],)).fetchone()
            if not row or json.loads(row[0])!=expected:raise ValueError('字型記錄已改變，請重新核對授權')
            self.library.db.execute('UPDATE font_assets SET payload=? WHERE hash=?',(json.dumps(updated,ensure_ascii=False),expected['hash']))
            self.library.event(expected['hash'],'font_output_rights_attested')
        return updated

    def import_font(self, path: str | Path, approved: bool = False, face_index: int | None = None,
                    usage_rights: dict | None = None) -> dict:
        from .font_evidence import inspect_font, face_bytes
        if not approved:
            raise ValueError("請先確認有權將此字型保存於本機並在程式使用")
        path = Path(path)
        proof = inspect_font(path)
        if face_index is None:
            if len(proof['faces']) != 1:
                raise ValueError("TTC含多個字面；請明確選取家族／款式後再匯入")
            face_index = 0
        data = face_bytes(path, face_index)
        if file_digest(path) != proof['hash']:
            raise ValueError("來源字型在解析期間已變更，未匯入")
        evidence = dict(proof['faces'][face_index], source_hash=proof['hash'],
                        source_name=path.name, collection=proof['collection'])
        rights = dict(usage_rights or {})
        if rights and (not isinstance(rights.get('actor'),str) or not rights['actor'].strip() or
                       not isinstance(rights.get('basis'),str) or not rights['basis'].strip() or
                       len(rights['basis']) > 2048 or len(rights['actor']) > 200 or
                       any(type(rights.get(key,False)) is not bool for key in ('print_export','pdf_embedding'))):
            raise ValueError("字型用途授權需要核准者、合法依據與明確用途")
        if not proof['collection']:
            return self._import_single(path, approved, evidence, rights, path.name)
        folder = self.library.assets / 'fonts'
        folder.mkdir(exist_ok=True)
        fd, name = tempfile.mkstemp(prefix='.face-',suffix='.otf',dir=folder)
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(data)
            return self._import_single(Path(name), approved, evidence, rights, path.name)
        finally:
            Path(name).unlink(missing_ok=True)

    def _import_single(self, path, approved, evidence, rights, original_name) -> dict:
        path = Path(path)
        if not approved:
            raise ValueError("請先確認有權將此字型保存於本機並在程式使用")
        if path.suffix.lower() not in (".ttf", ".otf", ".ttc") or not path.is_file() or path.stat().st_size > 50_000_000:
            raise ValueError("字型需為可讀 TTF／OTF／TTC，單檔不超過 50 MB")
        digest = file_digest(path)
        existing = next((asset for asset in self.library.fonts() if asset["hash"] == digest), None)
        if existing:
            errors = font_errors(existing, existing["families"][0])
            if errors:
                raise ValueError("；".join(errors) + "；請使用「修復既有本機字型」恢復同內容複本")
            if digest not in self.loaded:
                font_id = QFontDatabase.addApplicationFont(existing["path"])
                if font_id < 0:
                    raise ValueError("既有字型無法載入")
                self.loaded[digest] = (font_id, existing)
            return existing
        folder = self.library.assets / "fonts"
        folder.mkdir(exist_ok=True)
        target = folder / (digest + path.suffix.lower())
        fd, temporary_name = tempfile.mkstemp(prefix=".font-", suffix=path.suffix.lower(), dir=folder)
        os.close(fd)
        temporary = Path(temporary_name)
        created = False
        font_id = -1
        try:
            shutil.copyfile(path, temporary)
            if file_digest(temporary) != digest:
                raise ValueError("字型在複製期間變更，未保存")
            if target.exists():
                if file_digest(target) != digest:
                    raise ValueError("字型保存位置有不同內容，未覆寫")
            else:
                os.link(temporary, target)
                created = True
            font_id = QFontDatabase.addApplicationFont(str(target))
            families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
            if not families:
                raise ValueError("字型無法由 Qt 解析")
            if any(set(families).intersection(asset["families"]) for asset in self.library.fonts()):
                raise ValueError("同名字型家族已有不同檔案版本；本版不自動替換或混用，請先使用既有資產")
            asset = {"hash": digest, "path": str(target), "families": families,
                     "original_name": original_name, "approved": True,
                     "font_evidence": evidence, "usage_rights": rights}
            self.library.register_font(asset)
            self.loaded[digest] = (font_id, asset)
            return asset
        except BaseException:
            if font_id >= 0:
                QFontDatabase.removeApplicationFont(font_id)
            if created:
                target.unlink(missing_ok=True)
            raise
        finally:
            temporary.unlink(missing_ok=True)

    def _owned_target(self, asset: dict) -> Path:
        folder = self.library.assets / "fonts"
        target = Path(asset["path"])
        if (folder.resolve() != folder or target.parent != folder or target.suffix.lower() not in (".ttf", ".otf", ".ttc")
                or target.stem != asset["hash"] or target.is_symlink()):
            raise ValueError("字型修復位置不是程式擁有的正常複本，不修改此位置")
        return target

    def _recover_repairs(self) -> None:
        import json
        records=self.library.db.execute("SELECT hash,payload FROM font_repairs WHERE phase='PREPARED' ORDER BY rowid LIMIT 101").fetchall()
        if len(records)>100:self.issues.append('超過100件未完成修復；剩餘項留待字型管理中心核對')
        for asset_hash,raw in records[:100]:
            record=json.loads(raw)
            try:
                row=self.library.db.execute('SELECT payload FROM font_assets WHERE hash=?',(asset_hash,)).fetchone()
                if not row:raise ValueError('字型資產已失聯')
                asset=json.loads(row[0])
                self._owned_target(asset)
                valid = not font_errors(asset, asset["families"][0])
                if valid:
                    self.library.finish_font_repair(record["id"], "COMPLETED", "font_repair_recovered_same_content")
                else:
                    self.library.finish_font_repair(record["id"], "FAILED", "font_repair_interrupted_not_restored")
            except (KeyError, ValueError, OSError) as error:
                self.issues.append("未完成字型修復需處理：" + str(error))
            except Exception as error:
                self.issues.append("修復紀錄尚未安全保存：" + str(error))

    def repair_font(self, asset_hash: str, path: str | Path, approved: bool = False) -> dict:
        """同內容才能恢復 pin；損壞複本保留隔離，正常例外回滾，中斷靠意圖核對。"""
        if approved is not True:
            raise ValueError("請先確認有權將此字型保存於本機並在程式使用")
        asset = next((a for a in self.library.fonts() if a["hash"] == asset_hash), None)
        if not asset or asset.get("approved") is not True or not asset.get("families"):
            raise ValueError("沒有此既有核准字型資產，請先正常匯入")
        target = self._owned_target(asset)
        path = Path(path)
        if path.suffix.lower() not in (".ttf", ".otf", ".ttc") or not path.is_file() or path.stat().st_size > 50_000_000:
            raise ValueError("字型需為可讀 TTF／OTF／TTC，單檔不超過 50 MB")
        if file_digest(path) != asset_hash:
            raise ValueError("修復字型內容不符；同家族或檔名不能替換既有核准版本")
        if not font_errors(asset, asset["families"][0]):
            return self.import_font(path, approved=True)
        folder = target.parent
        folder.mkdir(exist_ok=True)
        repair_id = uuid.uuid4().hex
        quarantine = folder / "quarantine"
        quarantine.mkdir(exist_ok=True)
        if quarantine.is_symlink():
            raise ValueError("字型隔離位置含符號連結，未修復")
        backup = quarantine / (repair_id + target.suffix)
        fd, name = tempfile.mkstemp(prefix=".repair-", suffix=target.suffix, dir=folder)
        temporary = Path(name)
        new_font_id = -1
        replaced = False
        prepared = False
        committed = False
        existed = target.exists()
        try:
            with os.fdopen(fd, "wb") as stream, path.open("rb") as source:
                total = 0
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    total += len(chunk)
                    if total > 50_000_000:
                        raise ValueError("字型複製期間超過 50 MB，未修復")
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            if file_digest(temporary) != asset_hash:
                raise ValueError("字型複製期間變更，未修復")
            new_font_id = QFontDatabase.addApplicationFont(str(temporary))
            families = QFontDatabase.applicationFontFamilies(new_font_id) if new_font_id >= 0 else []
            if set(families) != set(asset["families"]):
                raise ValueError("修復字型無法由 Qt 解析或家族與原核准不符")
            self._owned_target(asset)
            original_hash = None
            if existed:
                if not target.is_file() or target.stat().st_size > 50_000_000:
                    raise ValueError("損壞字型複本無法安全隔離，未修復")
                original_hash = file_digest(target)
                with target.open("rb") as source, backup.open("xb") as saved:
                    shutil.copyfileobj(source, saved, length=1024 * 1024)
                    saved.flush()
                    os.fsync(saved.fileno())
                if file_digest(backup) != original_hash or file_digest(target) != original_hash:
                    raise ValueError("損壞複本在隔離期間變更，未修復")
            record = {"id": repair_id, "hash": asset_hash, "path": str(target), "approved": True,
                      "backup": str(backup) if existed else None, "previous_hash": original_hash,
                      "created": time.time()}
            self.library.prepare_font_repair(record)
            prepared = True
            # 意圖已持久化，再取得寫入鎖直到完成或檔案回滾，避免另一修復插入。
            self.library.db.execute("BEGIN IMMEDIATE")
            self._owned_target(asset)
            if target.exists() != existed or (existed and file_digest(target) != original_hash):
                raise ValueError("字型複本在修復前變更，未替換")
            os.replace(temporary, target)
            replaced = True
            self.library.finish_font_repair(repair_id, "COMPLETED", "font_repaired_same_content_approved")
            self.library.db.commit()
            committed = True
            old = self.loaded.pop(asset_hash, None)
            if old:
                QFontDatabase.removeApplicationFont(old[0])
            self.loaded[asset_hash] = (new_font_id, asset)
            new_font_id = -1
            self.issues = []
            for a in self.library.fonts():
                families = a.get("families", []) if isinstance(a, dict) else []
                self.issues.extend(font_errors(a, families[0] if isinstance(families, list) and families else ""))
            return asset
        except BaseException:
            if replaced and not committed:
                if existed:
                    # 保留隔離檔案供覆核，另複製回暫存再原子回復。
                    shutil.copyfile(backup, temporary)
                    os.replace(temporary, target)
                else:
                    target.unlink(missing_ok=True)
            if prepared and not committed:
                try:
                    self.library.finish_font_repair(repair_id, "FAILED", "font_repair_rolled_back")
                    self.library.db.commit()
                except Exception:
                    self.library.db.rollback()
                    pass  # PREPARED 保留，重開以实际 bytes 核對；不可冒稱完成。
            raise
        finally:
            if prepared and not committed and self.library.db.in_transaction:
                # 檔案回復本身失敗時也釋放鎖；意圖留待啟動實際核對。
                self.library.db.rollback()
            if new_font_id >= 0:
                QFontDatabase.removeApplicationFont(new_font_id)
            temporary.unlink(missing_ok=True)

    def close(self):
        for font_id, asset in self.loaded.values():
            QFontDatabase.removeApplicationFont(font_id)
        self.loaded.clear()
