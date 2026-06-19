#!/usr/bin/env python3
"""Bump charm/resource revisions in a Terraform configuration.

The file is parsed with ``python-hcl2``, but only the two target integer
literals are rewritten in place — formatting, comments, attribute order, and
line endings are preserved byte-for-byte.

For ``resource "juju_application" "<app>"`` the script updates:

* ``charm { revision = N }``
* ``resources = { <image_key> = N }``
"""

from __future__ import annotations

import argparse
from pathlib import Path

import hcl2
from lark import Token, Tree


class BumpError(Exception):
    """Raised when the expected Terraform structure cannot be edited."""


# AST helpers below navigate the lark tree produced by python-hcl2:
#   block         := identifier string* "{" body "}"
#   attribute     := identifier "=" expr_term
#   object_elem   := object_elem_key "=" expr_term
#   int_lit       := INT_LITERAL    (Token; carries .start_pos / .end_pos)
# All return ``None`` on a miss so callers stay branch-light.

def _child_trees(node: Tree, name: str):
    for child in node.children:
        if isinstance(child, Tree) and child.data == name:
            yield child


def _first_tree(node: Tree, name: str) -> Tree | None:
    return next(_child_trees(node, name), None)


def _name(identifier: Tree) -> str | None:
    for token in identifier.children:
        if isinstance(token, Token) and token.type == "NAME":
            return token.value
    return None


def _string_value(string_tree: Tree) -> str:
    parts: list[str] = []
    for part in _child_trees(string_tree, "string_part"):
        parts.extend(t.value for t in part.children if isinstance(t, Token))
    return "".join(parts)


def _block_type(block: Tree) -> str | None:
    identifier = _first_tree(block, "identifier")
    return _name(identifier) if identifier is not None else None


def _block_labels(block: Tree) -> list[str]:
    return [_string_value(s) for s in _child_trees(block, "string")]


def _block_body(block: Tree) -> Tree | None:
    return _first_tree(block, "body")


def _blocks(body: Tree):
    return _child_trees(body, "block")


def _attribute(body: Tree, name: str) -> Tree | None:
    for attr in _child_trees(body, "attribute"):
        identifier = _first_tree(attr, "identifier")
        if identifier is not None and _name(identifier) == name:
            return attr
    return None


def _int_token(expr_term: Tree | None) -> Token | None:
    if expr_term is None:
        return None
    int_lit = _first_tree(expr_term, "int_lit")
    if int_lit is None:
        return None
    for token in int_lit.children:
        if isinstance(token, Token) and token.type == "INT_LITERAL":
            return token
    return None


def _object_elem_key(elem: Tree) -> str | None:
    key = _first_tree(elem, "object_elem_key")
    if key is None:
        return None
    expr_term = _first_tree(key, "expr_term")
    if expr_term is None:
        return None
    identifier = _first_tree(expr_term, "identifier")
    if identifier is not None:
        return _name(identifier)
    string_tree = _first_tree(expr_term, "string")
    return _string_value(string_tree) if string_tree is not None else None


def _find_juju_application(tree: Tree, app_name: str) -> Tree | None:
    body = _first_tree(tree, "body")
    if body is None:
        return None
    for block in _blocks(body):
        labels = _block_labels(block)
        if (
            _block_type(block) == "resource"
            and len(labels) >= 2
            and labels[0] == "juju_application"
            and labels[1] == app_name
        ):
            return block
    return None


def _charm_revision_token(resource_body: Tree) -> Token | None:
    charm = next(
        (b for b in _blocks(resource_body) if _block_type(b) == "charm"), None
    )
    if charm is None:
        return None
    charm_body = _block_body(charm)
    if charm_body is None:
        return None
    revision = _attribute(charm_body, "revision")
    if revision is None:
        return None
    return _int_token(_first_tree(revision, "expr_term"))


def _resource_image_token(resource_body: Tree, key: str) -> Token | None:
    resources = _attribute(resource_body, "resources")
    if resources is None:
        return None
    obj = _first_tree(_first_tree(resources, "expr_term"), "object")
    if obj is None:
        return None
    for elem in _child_trees(obj, "object_elem"):
        if _object_elem_key(elem) == key:
            values = [c for c in elem.children if isinstance(c, Tree) and c.data == "expr_term"]
            return _int_token(values[-1]) if values else None
    return None


def _splice(text: str, edits: list[tuple[int, int, str]]) -> str:
    """Apply byte-range replacements right-to-left so earlier offsets stay valid."""
    for start, end, value in sorted(edits, key=lambda e: e[0], reverse=True):
        text = text[:start] + value + text[end:]
    return text


def bump_file(
    path: Path,
    app_name: str,
    charm_revision: int,
    resource_revision: int,
    image_key: str = "app-image",
) -> bool:
    """Rewrite charm and resource revisions in ``path``; return ``True`` if changed.

    Raises :class:`BumpError` if the targeted resource or either revision
    attribute cannot be located.
    """
    # ``newline=""`` disables universal-newline translation so we can detect
    # and faithfully restore the original line endings.
    with path.open("r", encoding="utf-8", newline="") as handle:
        original = handle.read()

    # The HCL parser only accepts LF, so normalise for parsing/editing and
    # re-apply the original CRLF endings on write.
    uses_crlf = "\r\n" in original
    text = original.replace("\r\n", "\n") if uses_crlf else original

    tree = hcl2.parses_to_tree(text)

    resource = _find_juju_application(tree, app_name)
    resource_body = _block_body(resource) if resource is not None else None

    charm_token = (
        _charm_revision_token(resource_body) if resource_body is not None else None
    )
    image_token = (
        _resource_image_token(resource_body, image_key)
        if resource_body is not None
        else None
    )

    missing: list[str] = []
    if charm_token is None:
        missing.append("charm revision")
    if image_token is None:
        missing.append(f"resource revision ({image_key})")
    if missing:
        raise BumpError(
            f"Failed to update {', '.join(missing)} in {path}. "
            f'Expected to find resource "juju_application" "{app_name}" with '
            "charm { revision = N } and resources = { " + image_key + " = N }."
        )

    edits = [
        (charm_token.start_pos, charm_token.end_pos, str(charm_revision)),
        (image_token.start_pos, image_token.end_pos, str(resource_revision)),
    ]
    updated = _splice(text, edits)

    if updated == text:
        return False

    if uses_crlf:
        updated = updated.replace("\n", "\r\n")
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(updated)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bump charm/resource revisions in a Terraform main.tf."
    )
    parser.add_argument("--file", required=True, help="Path to main.tf (or equivalent).")
    parser.add_argument(
        "--app-name", default="app", help="Name of the juju_application resource."
    )
    parser.add_argument("--charm-revision", required=True, type=int)
    parser.add_argument("--resource-revision", required=True, type=int)
    parser.add_argument(
        "--image-key",
        default="app-image",
        help="Key in the resources map to update (default: app-image).",
    )
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    try:
        changed = bump_file(
            path=path,
            app_name=args.app_name,
            charm_revision=args.charm_revision,
            resource_revision=args.resource_revision,
            image_key=args.image_key,
        )
    except BumpError as error:
        raise SystemExit(str(error))

    print(f"Updated {path}" if changed else f"No changes needed in {path}")


if __name__ == "__main__":
    main()
