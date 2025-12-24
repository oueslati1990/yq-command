import argparse
import sys
import yaml
import re

def read_file(filename):
    """Reads a yaml file"""
    with open(filename, 'r') as f:
        return yaml.safe_load(f)

def parse_query(query):
    """Parse the query expression to extract the key and optional flag"""
    # Match patterns like .[key], .["key"], .key, .key?, etc.
    patterns = [
        r'^\.\[(["\']?)([^"\'\]]+)\1\]\??$',  # .[key] or .["key"] or .['key'] with optional ?
        r'^\.([a-zA-Z_][a-zA-Z0-9_]*)\??$'     # .key with optional ?
    ]

    for pattern in patterns:
        match = re.match(pattern, query)
        if match:
            # Extract the key (last group is the key name)
            groups = match.groups()
            key = groups[-1] if len(groups) > 1 else groups[0]
            optional = query.endswith('?')
            return key, optional

    return None, False

def apply_query(data, query):
    """Apply the query to the data"""
    if not query or query == '.':
        return data

    key, optional = parse_query(query)

    if key is None:
        if not optional:
            raise ValueError(f"Invalid query expression: {query}")
        return None

    if isinstance(data, dict):
        if key in data:
            return data[key]
        elif not optional:
            raise KeyError(f"Key '{key}' not found")
    elif not optional:
        raise TypeError(f"Cannot index {type(data).__name__} with key")

    return None

def main():
    """Main logic"""
    parser = argparse.ArgumentParser(
        description="ccyq command"
    )
    parser.add_argument('query', nargs='?', default='.',
                        help="query expression (e.g., .quotes, .[quotes], .quotes?)")
    parser.add_argument('filename', nargs='?', default=None,
                        help="file to read")
    args = parser.parse_args()

    content = ''
    try:
        if args.filename:
            content = read_file(args.filename)
        else:
            stdin_content = sys.stdin.buffer.read().decode('utf-8')
            content = yaml.safe_load(stdin_content)
    except FileNotFoundError:
        print(f'file {args.filename} does not exist', file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f'You are not permitted to access this file : {args.filename}', file=sys.stderr)
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
            print(yaml.dump(result, default_flow_style=False, sort_keys=False), end='')
    except (KeyError, ValueError, TypeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()