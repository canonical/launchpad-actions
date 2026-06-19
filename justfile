default:
    @just --list

test:
    cd actions/terraform-bump-pr && uv run --locked python -m unittest discover -p 'test_*.py' -v
