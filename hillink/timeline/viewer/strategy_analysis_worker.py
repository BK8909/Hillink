"""Child process for per-run strategy provider mode; no shared env mutation."""
import json,sys
import strategy_agent_service as service

if __name__=='__main__':
    value=json.load(sys.stdin)
    print(json.dumps(service.analyze(value['request'],value['bundles'],value['source']),ensure_ascii=False))
