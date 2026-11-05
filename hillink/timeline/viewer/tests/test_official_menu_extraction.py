from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from audit_official_menu import validate

def row():
 return dict(page=27,name_verbatim='북경식 탕수육',price_krw=105000,source_excerpt='북경식 탕수육 105,000')

def test_source_match_never_grants_runtime_or_semantic_approval():
 item=validate(dict(items=[row()]),[dict(page=27,text='북경식 탕수육 105,000 (돼지고기)')])[0]
 assert item['automatic_choice'] is False
 assert item['review_status']=='SOURCE_TEXT_MATCHED_SEMANTIC_REVIEW_REQUIRED'

@pytest.mark.parametrize('change,reason',[({'page':28},'PAGE_OUTSIDE_BATCH'),({'name_verbatim':'없는 요리'},'NAME_NOT_VERBATIM'),({'price_krw':1},'PRICE_NOT_PRINTED'),({'source_excerpt':'돼지고기 105,000'},'EXCERPT_NOT_VERBATIM')])
def test_unverified_extraction_is_rejected(change,reason):
 with pytest.raises(ValueError,match=reason):
  validate(dict(items=[dict(row(),**change)]),[dict(page=27,text='북경식 탕수육 105,000 (돼지고기)')])
def test_embedded_digit_font_decoding_is_source_bound():
 from audit_official_menu import source_text,DIGIT_FONT_SOURCE_SHA
 text='Wine '+chr(0xf357)+chr(0xf358)+chr(0xf356)+','+chr(0xf356)*3
 assert source_text(text,'different-source')==text
 assert source_text(text,DIGIT_FONT_SOURCE_SHA)=='Wine 120,000'
 assert source_text(''.join(chr(0xf356+n) for n in range(10)),DIGIT_FONT_SOURCE_SHA)=='0123456789'
 assert validate(dict(items=[dict(page=2,name_verbatim='Wine',source_excerpt='Wine 120,000',price_krw=120000)]),[dict(page=2,text=source_text(text,DIGIT_FONT_SOURCE_SHA))])[0]['automatic_choice'] is False
