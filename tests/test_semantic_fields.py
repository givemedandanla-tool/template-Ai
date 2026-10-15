import unittest
from template_ai.semantic_fields import recognize,CharacterModel


class SemanticFieldTests(unittest.TestCase):
    def check_type(self,value,kind,slot=None,**kwargs):
        row=recognize(value,**kwargs);self.assertEqual(row['semantic_type'],kind,row)
        if slot:self.assertEqual(row['slot_kind'],slot)
        self.assertEqual(row['state'],'PENDING_REVIEW');self.assertTrue(row['signals']);return row

    def test_email_fullwidth_labels_and_social_handles_are_separate(self):
        row=self.check_type('電子郵件：ａｌｅｘ＠ｅｘａｍｐｌｅ．ｔｅｓｔ','email','email')
        self.assertEqual(row['raw'],'電子郵件：ａｌｅｘ＠ｅｘａｍｐｌｅ．ｔｅｓｔ');self.assertEqual(row['normalized'],'alex@example.test')
        self.check_type('LINE: @example.team','social_id','line');self.check_type('IG：example.team','social_id','ig')
        self.check_type('@example.team','unknown');self.check_type('not-an-email@','unknown')

    def test_phone_metadata_distinguishes_taiwan_mobile_landline_extension_and_fax(self):
        self.check_type('手機：0912-345-678','mobile','phone');self.check_type('+886 912345678','mobile','phone')
        row=self.check_type('市內電話：(02) 2345-6789 分機123','landline','phone');self.assertEqual(row['normalized'],'+886223456789 ext. 123')
        self.check_type('FAX: 02-2345-6789','fax','phone')
        self.check_type('手機：12345','unknown');self.check_type('訂單 202610151234','unknown')
        self.check_type('0000000000','unknown')

    def test_international_ambiguous_phone_and_contradictory_labels_remain_reviewable(self):
        self.check_type('+44 20 7946 0958','landline','phone')
        row=self.check_type('+1 202 555 0123','phone','phone');self.assertEqual(row['confidence'],'UNCALIBRATED_CANDIDATE')
        row=self.check_type('手機：02-2345-6789','landline');self.assertTrue(any('矛盾' in s for s in row['signals']))

    def test_explicit_platform_urls_do_not_turn_generic_urls_or_email_into_social_ids(self):
        self.check_type('https://instagram.com/example.team','social_id','ig')
        row=self.check_type('https://t.me/example_team','social_id');self.assertEqual(row['platform'],'telegram');self.assertIsNone(row['slot_kind'])
        self.check_type('https://example.test/instagram.com/alex','unknown');self.check_type('alex@instagram.com','email')

    def test_address_title_company_meaning_and_counterexamples(self):
        for text in ('台北市信義區信義路五段7號','地址：新竹市東區光復路二段101號','123 Main Street, London'):
            self.check_type(text,'address','address')
        for text in ('總經理','工程師','Software Engineer','Senior Manager','CEO','職稱：資深產品顧問'):
            self.check_type(text,'title','title')
        self.check_type('範例股份有限公司','company','company');self.check_type('姓名：王範例','name','name')
        for text in ('台北','Main Street','經理電話簿','12345','王範例','example.team'):
            self.check_type(text,'unknown')

    def test_authorized_character_model_generalizes_without_promoting_unconfirmed_samples(self):
        rows=[]
        for kind,texts in {'title':['資深雲端工程師','資深後端工程師','資深軟體工程師'], 'address':['台中市西區公益路10號','台中市西區中正路20號','台中市西區民生路30號']}.items():
            for value in texts:rows.append(dict(sample_id=str(len(rows)),text=value,semantic_type=kind,confirmed=True,use='SEMANTIC_CLASSIFICATION_LOCAL'))
        rows.append(dict(sample_id='unconfirmed',text='資深前端工程師',semantic_type='address',confirmed=False,use='SEMANTIC_CLASSIFICATION_LOCAL'))
        rows.append(dict(sample_id='geometry-only',text='資深前端工程師',semantic_type='address',confirmed=True,use='GEOMETRY_TRAINING_LOCAL'))
        model=CharacterModel(rows);self.assertEqual(len(model.sample_ids),6)
        row=recognize('資深前端工程師',model=model);self.assertEqual(row['semantic_type'],'title');self.assertIsNotNone(row['model']);self.assertEqual(row['model']['score_kind'],'UNCALIBRATED_LOG_LIKELIHOOD_MARGIN')
        self.check_type('qzxv98765','unknown',model=model);self.check_type('@front.engineer','unknown',model=model)
        self.assertIsNone(CharacterModel(rows[:1]).predict('資深工程師'))

    def test_bounded_input_rejects_binary_text_floods_and_control_characters(self):
        for value in ('', 'x'*2049, 'a\x00b',None):
            with self.assertRaises(ValueError):recognize(value)
