"""CLI entry point for schema-salad-plus-pydantic."""

from __future__ import annotations

import argparse
import sys

from .orchestrate import generate_from_schema


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="schema-salad-plus-pydantic",
        description="Generate pydantic v2 models from schema-salad definitions",
    )
    subparsers = parser.add_subparsers(dest="command")

    gen_parser = subparsers.add_parser("generate", help="Generate pydantic models")
    gen_parser.add_argument("schema", help="Schema-salad YAML file")
    gen_parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    gen_parser.add_argument("--copyright", help="Copyright notice")
    gen_parser.add_argument("--parser-info", default="", help="Parser info string")

    args = parser.parse_args(argv)

    if args.command == "generate":
        if args.output:
            with open(args.output, "w") as f:
                generate_from_schema(args.schema, f, copyright=args.copyright, parser_info=args.parser_info)
        else:
            generate_from_schema(args.schema, sys.stdout, copyright=args.copyright, parser_info=args.parser_info)
    else:
        parser.print_help()
        sys.exit(1)
