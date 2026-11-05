import argparse,json,sys
from pathlib import Path
from experiment_service import run_request,default_request

def main():
    ap=argparse.ArgumentParser(description='CD-1024-15 isolated dinner scenario runner')
    ap.add_argument('request',nargs='?',help='JSON request path; omitted uses CD-14 base request')
    ap.add_argument('--out',required=True,help='output JSON path')
    args=ap.parse_args()
    try:
        req=json.loads(Path(args.request).read_text()) if args.request else default_request()
        result=run_request(req)
    except Exception as e:
        msg=str(e).splitlines()[0][:240]
        if any(token in msg for token in ('/private/','/Users/','Application Support','turn_personas_ext.local')):
            msg='required_local_input_unavailable_or_invalid'
        if isinstance(e,FileNotFoundError):
            msg='required_local_input_unavailable'
        result={'schema_version':'cd1024-15-output-v1','experiment':{'run_status':'INVALID_REQUEST'},'error':{'code':type(e).__name__,'message':msg}}
        Path(args.out).write_text(json.dumps(result,ensure_ascii=False,indent=2))
        return 2
    Path(args.out).write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({'run_status':result['experiment']['run_status'],'scenario_input_sha256':result['experiment']['scenario_input_sha256'],'selected_offer_ids':result['experiment'].get('selected_offer_ids',[]),'venue_aggregates':result['venue_aggregates']},ensure_ascii=False))
    return 0
if __name__=='__main__': sys.exit(main())
