"""Offline caller-supplied private corpus runner. Never invokes an LLM/provider."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from .pilot import run_private, public_projection, validate_public_projection, write_private_only


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-input-directory",type=Path,required=True)
    parser.add_argument("--private-output-directory",type=Path,required=True)
    parser.add_argument("--safe-output-directory",type=Path)
    args=parser.parse_args()
    root=args.private_input_directory.resolve()
    if any((p/".git").exists() for p in (root,*root.parents)):
        parser.error("raw input must be outside Git worktrees")
    documents=json.loads((root/"documents.json").read_text())
    annotations=json.loads((root/"annotations.json").read_text())
    assertions=json.loads((root/"assertions.json").read_text())
    result=run_private(documents,annotations,assertions)
    write_private_only(args.private_output_directory,result)
    if args.safe_output_directory:
        safe=public_projection(result)
        if validate_public_projection(safe):
            raise ValueError("safe_projection_failed_do_not_publish")
        out=args.safe_output_directory.resolve()
        out.mkdir(parents=True,exist_ok=True)
        target=out/"profiles_and_quality.json"
        if target.exists():
            raise FileExistsError("version_public_results_do_not_overwrite")
        encoded=(json.dumps(safe,ensure_ascii=False,indent=2)+"\n").encode()
        target.write_bytes(encoded)
        module_root=Path(__file__).parent
        code_hashes={p.name:sha256(p.read_bytes()).hexdigest() for p in sorted(module_root.iterdir()) if p.suffix in {".py",".json",".md"}}
        manifest={"method_version":safe["version"],"result_sha256":sha256(encoded).hexdigest(),
                  "method_file_sha256":code_hashes,
                  "source_content_included":False,"raw_source_hashes_included":False,
                  "extraction_mode":"analyst_source_checks_plus_separate_lexical_retrieval", "separate_model_calls":0,
                  "product_api_calls":0,"human_review":"pending","demo_approved":False,
                  "local_processing_seconds_excluding_reading_annotation_and_review":result["local_processing_seconds"],
                  "reproduction_requires_restricted_corpus_and_annotation_registry":True}
        (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"author_count":len(result["authors"]),"separate_model_calls":0,"human_review":"pending"}))


if __name__ == "__main__":
    main()
