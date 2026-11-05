"""Private local preparation/import only. No LLM execution, API or model adapter."""
import argparse
import json
from pathlib import Path

from .study import prepare_requests,validate_import
from .team_contract import prepare_team_requests,import_team_profile


def private_path(value):
    root=Path(value).resolve()
    if any((p/".git").exists() for p in (root,*root.parents)):
        raise ValueError("private_source_or_output_must_be_outside_git_worktrees")
    return root


def save_private(directory,name,value):
    root=private_path(directory)
    if Path(name).name!=name or name in {".",".."}:
        raise ValueError("private_output_filename_must_be_local_to_directory")
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    target=root/name
    # x mode: no silent overwrite of an earlier packet or raw imported response.
    with target.open("x",encoding="utf-8") as stream:
        target.chmod(0o600)
        json.dump(value,stream,ensure_ascii=False,indent=2)
        stream.write("\n")
    return target


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest="command",required=True)
    prepare=commands.add_parser("prepare")
    prepare.add_argument("--private-corpus",type=Path,required=True)
    prepare.add_argument("--author-id",required=True)
    prepare.add_argument("--author-role",choices=("method_development","transfer_check_prior_research","holdout_new_author"),required=True)
    prepare.add_argument("--private-photo-notes",type=Path)
    prepare.add_argument("--contract",choices=("received-team-v41","native-v41"),default="received-team-v41")
    prepare.add_argument("--private-primary-type",type=Path)
    prepare.add_argument("--private-excluded-posts",type=Path)
    prepare.add_argument("--private-output-directory",type=Path,required=True)
    ingest=commands.add_parser("import-response")
    ingest.add_argument("--private-packet",type=Path,required=True)
    ingest.add_argument("--private-response",type=Path,required=True)
    ingest.add_argument("--request-id",required=True)
    ingest.add_argument("--private-output-directory",type=Path,required=True)
    team_ingest=commands.add_parser("import-team-response")
    team_ingest.add_argument("--private-corpus",type=Path,required=True)
    team_ingest.add_argument("--private-packet",type=Path,required=True)
    team_ingest.add_argument("--private-response",type=Path,required=True)
    team_ingest.add_argument("--private-output-directory",type=Path,required=True)
    args=parser.parse_args()
    def load(path): return json.loads(private_path(path).read_text())
    if args.command=="prepare":
        docs=[d for d in load(args.private_corpus) if d["persona_id"]==args.author_id]
        if not docs:
            parser.error("authorized raw posts for this author are not available; no profile or packet was generated")
        notes=load(args.private_photo_notes) if args.private_photo_notes else None
        if args.contract=="received-team-v41":
            result=prepare_team_requests(docs,author_role=args.author_role,photo_notes=notes,
                                        primary_type=load(args.private_primary_type) if args.private_primary_type else None,
                                        excluded_posts=load(args.private_excluded_posts) if args.private_excluded_posts else [])
            post_count=len(docs); request_count=result["prepared_author_request_count"]
        else:
            result=prepare_requests(docs,author_role=args.author_role,notes_by_post=notes or {})
            post_count=result["prepared_post_count"]; request_count=len(result["requests_private"])
        save_private(args.private_output_directory,"extraction_packet_private.json",result)
        print(json.dumps({"prepared_posts":post_count,"prepared_requests":request_count,
                          "actual_executions":0,"independent_quality_established":False}))
    else:
        packet=load(args.private_packet); raw=load(args.private_response)
        # Preserve submitted original response separately from validation output.
        save_private(args.private_output_directory,"raw_response_private.json",raw)
        try:
            if args.command=="import-team-response":
                if not raw.get("actual_model_id") or not raw.get("actual_session_ref") or not raw.get("isolation_description") or raw.get("input_sha256_private")!=packet["input_sha256_private"]:
                    raise ValueError("actual_model_session_and_matching_team_input_required")
                docs=[d for d in load(args.private_corpus) if d["persona_id"]==packet["persona_id"]]
                result=import_team_profile(docs,packet,raw["profile"])
            else:
                result=validate_import(packet,args.request_id,raw)
        except (ValueError,KeyError,TypeError) as error:
            save_private(args.private_output_directory,"import_status_private.json",{"status":"quarantined","error":str(error),"automatic_retry":False})
            raise
        save_private(args.private_output_directory,"import_status_private.json",result)
        print(json.dumps({"structural_status":result["structural_status"],"semantic_review":"pending","demo_approved":False}))


if __name__=="__main__":
    main()
