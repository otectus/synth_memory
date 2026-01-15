import argparse
import sys
import json
from ..config.loader import ConfigurationLoader

def main():
    parser = argparse.ArgumentParser(description="SynthMemory Admin CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Show
    subparsers.add_parser("show", help="Show current configuration")

    # Set
    set_parser = subparsers.add_parser("set", help="Update a setting")
    set_parser.add_argument("key", help="Hierarchical key (e.g. performance.vector_k)")
    set_parser.add_argument("value", help="New value")

    # Validate
    subparsers.add_parser("validate", help="Run safety checks on current config")

    args = parser.parse_args()
    loader = ConfigurationLoader()

    if args.command == "show":
        config = loader.load()
        print(config.json(indent=2))

    elif args.command == "set":
        config = loader.load()
        parts = args.key.split(".")
        target = config
        for part in parts[:-1]:
            target = getattr(target, part)
        
        # Basic type inference from existing value
        current_val = getattr(target, parts[-1])
        if isinstance(current_val, int): val = int(args.value)
        elif isinstance(current_val, float): val = float(args.value)
        elif isinstance(current_val, bool): val = args.value.lower() == 'true'
        else: val = args.value

        setattr(target, parts[-1], val)
        loader.save(config)
        print(f"Set {args.key} to {val}")

    elif args.command == "validate":
        from ..config.validator import ConfigurationValidator
        config = loader.load()
        success, warnings = ConfigurationValidator.validate(config)
        if not success:
            for w in warnings: print(w)
        else:
            print("Configuration is healthy.")

if __name__ == "__main__":
    main()