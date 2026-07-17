"""mapmatching4gmns command-line entry (spec §1). Subcommands: self-demo, apply-review."""
import sys


def cli(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] == "self-demo":
        from .selfdemo import main
        return main(argv[1:])
    if argv and argv[0] == "apply-review":
        print("apply-review: human-in-the-loop path regeneration — Milestone 4 (stub)")
        return 0
    print("usage: mapmatching4gmns self-demo --case <name> [--all]\n"
          "       mapmatching4gmns apply-review <case_output/> --review match_review.csv")
    return 1


if __name__ == "__main__":
    sys.exit(cli())
