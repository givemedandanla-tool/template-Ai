"""像素比對只報測量結果，不用任意相似度門檻冒稱視覺已驗收。"""
from PySide6.QtGui import QImage


def compare_images(a: QImage, b: QImage) -> dict:
    if a.isNull() or b.isNull():
        raise ValueError("比對圖片不可讀")
    if a.size() != b.size():
        return {"status": "尺寸不同，需人工配準核對", "mean_difference": None}
    a = a.convertToFormat(QImage.Format_RGBA8888)
    b = b.convertToFormat(QImage.Format_RGBA8888)
    total = 0
    changed = 0
    # 逐列處理避免另外建立巨大的 NumPy 陣列與記憶體複本。
    for y in range(a.height()):
        aa, bb = bytes(a.constScanLine(y)[:a.width()*4]), bytes(b.constScanLine(y)[:b.width()*4])
        for av, bv in zip(aa, bb):
            difference = abs(av-bv)
            total += difference
            changed += difference != 0
    return {"status": "像素完全一致" if changed == 0 else "存在差異，需人工視覺核對", "mean_difference": total/(a.width()*a.height()*4), "changed_channels": changed}
