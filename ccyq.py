import argparse
import sys

def read_file(filename):
    """Reads a yaml file"""
    with open(filename, 'r') as f:
        return f.read()

def main():
    """Main logic"""
    parser = argparse.ArgumentParser(
        description="ccyq command"
    )
    parser.add_argument('filename', nargs='?', default=None,
                        help="file to read")
    args = parser.parse_args()

    content = ''
    try:
        if args.filename:
            content = read_file(args.filename)
        else:
            content = sys.stdin.buffer.read().decode('utf-8')
    except FileNotFoundError:
        print(f'file {args.filename} does not exist', file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f'You are not permitted to access this file : {args.filename}', file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"{args.filename}: {e}", file=sys.stderr)
        sys.exit(1) 

    print(content)

if __name__ == '__main__':
    main()