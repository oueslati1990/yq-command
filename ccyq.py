import argparse
import sys
import yaml
import re


def read_file(filename):
    """Reads a yaml file"""
    with open(filename, "r") as f:
        return yaml.safe_load(f)


def parse_query(query):
    """Parse the query expression to extract the key and optional flag"""
    # Match patterns like .[key], .["key"], .key, .key[0], etc.
    patterns = [
        r'^\.\["([^"]+)"\]\??$',  # .["key"] or .["key[0]"] with optional ?
        r"^\.\['([^']+)'\]\??$",  # .['key'] or .['key[0]'] with optional ?
        r"^\.\[([^\]]+)\]\??$",  # .[key] or .[key[0]] with optional ?
        r"^\.([a-zA-Z_][a-zA-Z0-9_]*(?:\[[^\]]*\])*)\??$",  # .key or .key[0] with optional ?
    ]

    for pattern in patterns:
        match = re.match(pattern, query)
        if match:
            # Extract the key from the captured group
            key = match.group(1)
            optional = query.endswith("?")
            return key, optional

    return None, False


def parse_key(key):
    """Parses key value and key value member index to access"""
    if "[" in key or "]" in key:
        if not ("[" in key and "]" in key):
            raise ValueError(f"Malformed key: '{key}' - missing bracket")

        open_bracket = key.index("[")
        close_bracket = key.index("]")

        if open_bracket >= close_bracket:
            raise ValueError(f"Malformed key: '{key}' - brackets in wrong order")

        key_v = key[:open_bracket]
        memb_index_str = key[open_bracket + 1 : close_bracket]
        try:
            memb_index = int(memb_index_str)
        except ValueError:
            raise ValueError(f"Index should be a digit, got : {memb_index_str}")

        if not key_v:
            raise ValueError(f"Malformed key: '{key}' - empty key name")

        return key_v, memb_index
    else:
        return key, None


def apply_query(data, query):
    """Apply the query to the data"""
    if not query or query == ".":
        return data

    key, optional = parse_query(query)

    if key is None:
        if not optional:
            raise ValueError(f"Invalid query expression: {query}")
        return None

    if isinstance(data, dict):
        key_val, member_index = parse_key(key)
        if key_val in data:
            if member_index is None:
                return data[key_val]
            else:
                return data[key_val][member_index]
        elif not optional:
            raise KeyError(f"Key '{key_val}' not found")
    elif not optional:
        raise TypeError(f"Cannot index {type(data).__name__} with key")

    return None


def main():
    """Main logic"""
    parser = argparse.ArgumentParser(description="ccyq command")
    parser.add_argument(
        "query",
        nargs="?",
        default=".",
        help="query expression (e.g., .quotes, .[quotes], .quotes?)",
    )
    parser.add_argument("filename", nargs="?", default=None, help="file to read")
    args = parser.parse_args()

    content = ""
    try:
        if args.filename:
            content = read_file(args.filename)
        else:
            stdin_content = sys.stdin.buffer.read().decode("utf-8")
            content = yaml.safe_load(stdin_content)
    except FileNotFoundError:
        print(f"file {args.filename} does not exist", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(
            f"You are not permitted to access this file : {args.filename}",
            file=sys.stderr,
        )
        sys.exit(1)
    except IOError as e:
        print(f"{args.filename}: {e}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"YAML parsing error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        result = apply_query(content, args.query)
        if result is not None:
            print(yaml.dump(result, default_flow_style=False, sort_keys=False), end="")
    except (KeyError, ValueError, TypeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
