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
    # Match patterns like .[key], .["key"], .key, .key[0], .key[].field, etc.
    patterns = [
        r'^\.\["([^"]+)"\]\??$',  # .["key"] or .["key[0]"] with optional ?
        r"^\.\['([^']+)'\]\??$",  # .['key'] or .['key[0]'] with optional ?
        r"^\.\[([^\]]+)\]\??$",  # .[key] or .[key[0]] with optional ?
        r"^\.([a-zA-Z_][a-zA-Z0-9_]*(?:\[[^\]]*\])*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\??$",  # .key, .key[0], .key[].field, etc. with optional ?
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
    """Parses key value and key value member index to access
    Returns: (key_name, member_index, remaining_key)
    - member_index can be an int, "iterate", or None
    - remaining_key is any part after the brackets (e.g., ".quote" in "quotes[].quote")
    """
    if "[" in key or "]" in key:
        if not ("[" in key and "]" in key):
            raise ValueError(f"Malformed key: '{key}' - missing bracket")

        open_bracket = key.index("[")
        close_bracket = key.index("]")

        if open_bracket >= close_bracket:
            raise ValueError(f"Malformed key: '{key}' - brackets in wrong order")

        key_v = key[:open_bracket]
        memb_index_str = key[open_bracket + 1 : close_bracket]
        remaining = key[close_bracket + 1:]  # Everything after ]

        # Handle empty brackets [] for iteration
        if memb_index_str == "":
            if not key_v:
                # Just [] without a key
                return "", "iterate", remaining
            return key_v, "iterate", remaining

        try:
            memb_index = int(memb_index_str)
        except ValueError:
            raise ValueError(f"Index should be a digit, got : {memb_index_str}")

        if not key_v:
            raise ValueError(f"Malformed key: '{key}' - empty key name")

        return key_v, memb_index, remaining
    else:
        return key, None, ""


def apply_query(data, query):
    """Apply the query to the data
    Can return a single value or a list of values (when iterating with [])
    """
    if not query or query == ".":
        return data

    if "|" in query:
        # Split by pipe and apply filters sequentially
        filters = [f.strip() for f in query.split("|")]
        result = data
        for filter_expr in filters:
            result = apply_query(result, filter_expr)
            # If the result is a list from iteration, apply subsequent filters to each element
            if isinstance(result, list) and filters.index(filter_expr) < len(filters) - 1:
                # There are more filters to apply
                remaining_filters = filters[filters.index(filter_expr) + 1:]
                results = []
                for item in result:
                    item_result = item
                    for remaining_filter in remaining_filters:
                        item_result = apply_query(item_result, remaining_filter)
                    results.append(item_result)
                return results
        return result

    key, optional = parse_query(query)

    if key is None:
        if not optional:
            raise ValueError(f"Invalid query expression: {query}")
        return None

    if isinstance(data, dict):
        key_val, member_index, remaining = parse_key(key)

        if key_val in data:
            value = data[key_val]

            # Handle iteration with []
            if member_index == "iterate":
                if not isinstance(value, list):
                    if not optional:
                        raise TypeError(f"Cannot iterate over {type(value).__name__}")
                    return None

                # If there's remaining query (e.g., ".quote" in "quotes[].quote")
                if remaining:
                    # Apply remaining query to each element
                    results = []
                    for item in value:
                        result = apply_query(item, "." + remaining.lstrip("."))
                        results.append(result)
                    return results
                else:
                    # No remaining query, just return all elements
                    return value

            # Handle specific index
            elif member_index is not None:
                result = value[member_index]
                # If there's remaining query after the index
                if remaining:
                    return apply_query(result, "." + remaining.lstrip("."))
                return result

            # No index, just return the value
            else:
                return value

        elif not optional:
            raise KeyError(f"Key '{key_val}' not found")

    # Handle iteration on just [] (without a key)
    elif isinstance(data, list) and key == "":
        key_val, member_index, remaining = parse_key(key) if "[" in key else ("", None, "")
        if member_index == "iterate":
            if remaining:
                results = []
                for item in data:
                    result = apply_query(item, "." + remaining.lstrip("."))
                    results.append(result)
                return results
            return data

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
        query = args.query
        collect_array = False

        # Check if query is wrapped in brackets for array collection
        if query.startswith("[") and query.endswith("]") and len(query) > 2:
            collect_array = True
            query = query[1:-1]  # Strip outer brackets

        result = apply_query(content, query)

        # If collect_array is True, ensure result is always a list
        if collect_array and not isinstance(result, list):
            result = [result] if result is not None else []

        if result is not None:
            print(yaml.dump(result, default_flow_style=False, sort_keys=False), end="")
    except (KeyError, ValueError, TypeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
