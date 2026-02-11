#!/usr/bin/env python3
"""
Setup verification script for Claude Agent SDK.

This script verifies that:
1. Python version is compatible
2. Claude Agent SDK is installed
3. Required environment variables are set
4. All imports work correctly
"""
import sys
import os
from pathlib import Path


def check_python_version():
    """Verify Python version meets minimum requirements."""
    print("🐍 Checking Python version...")
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    print(f"   Python version: {version_str}")

    if version.major == 3 and version.minor >= 10:
        print("   ✅ Python version is compatible (3.10+)")
        return True
    else:
        print(f"   ❌ Python version {version_str} is not supported")
        print("   Claude Agent SDK requires Python 3.10 or higher")
        return False


def check_sdk_installation():
    """Verify Claude Agent SDK is installed."""
    print("\n📦 Checking Claude Agent SDK installation...")
    try:
        import claude_agent_sdk
        version = claude_agent_sdk.__version__
        print(f"   Installed version: {version}")
        print("   ✅ Claude Agent SDK is installed")
        return True
    except ImportError as e:
        print("   ❌ Claude Agent SDK is not installed")
        print(f"   Error: {e}")
        print("\n   Install with: uv pip install claude-agent-sdk")
        return False


def check_imports():
    """Verify all required imports work."""
    print("\n📚 Checking imports...")
    required_imports = [
        ("claude_agent_sdk", ["query", "ClaudeAgentOptions", "AssistantMessage", "TextBlock", "ResultMessage"]),
        ("dotenv", ["load_dotenv"]),
        ("anthropic", None),  # Base dependency
    ]

    all_passed = True
    for module_name, items in required_imports:
        try:
            module = __import__(module_name)
            if items:
                for item in items:
                    if not hasattr(module, item):
                        print(f"   ❌ {module_name}.{item} not found")
                        all_passed = False
                    else:
                        print(f"   ✅ {module_name}.{item}")
            else:
                print(f"   ✅ {module_name}")
        except ImportError as e:
            print(f"   ❌ Cannot import {module_name}: {e}")
            all_passed = False

    return all_passed


def check_environment():
    """Verify environment is properly configured."""
    print("\n🔑 Checking environment configuration...")

    # Load .env if it exists
    from dotenv import load_dotenv
    env_file = Path(".env")

    if not env_file.exists():
        print("   ⚠️  .env file not found")
        print("   Create one from .env.example:")
        print("      cp .env.example .env")
        print("   Then add your ANTHROPIC_API_KEY")
        return False

    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        # Don't print the actual key
        masked_key = api_key[:8] + "..." if len(api_key) > 8 else "***"
        print(f"   ✅ ANTHROPIC_API_KEY is set ({masked_key})")
        return True
    else:
        print("   ❌ ANTHROPIC_API_KEY is not set in .env")
        print("   Get your API key from: https://console.anthropic.com/")
        return False


def check_example_files():
    """Verify example files exist."""
    print("\n📄 Checking example files...")

    files = [
        ("sre_agent_example.py", "SRE Agent example"),
        ("AGENT_SDK_GUIDE.md", "SDK documentation"),
        (".env.example", "Environment template"),
    ]

    all_exist = True
    for filename, description in files:
        path = Path(filename)
        if path.exists():
            print(f"   ✅ {filename} ({description})")
        else:
            print(f"   ❌ {filename} not found")
            all_exist = False

    return all_exist


def main():
    """Run all verification checks."""
    print("="*70)
    print("🔍 Claude Agent SDK Setup Verification")
    print("="*70)

    checks = [
        ("Python Version", check_python_version),
        ("SDK Installation", check_sdk_installation),
        ("Imports", check_imports),
        ("Environment", check_environment),
        ("Example Files", check_example_files),
    ]

    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"\n❌ Error during {name} check: {e}")
            results[name] = False

    # Summary
    print("\n" + "="*70)
    print("📊 Verification Summary")
    print("="*70)

    all_passed = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status:>10} - {name}")
        if not passed:
            all_passed = False

    print("="*70)

    if all_passed:
        print("\n🎉 All checks passed! Your setup is ready.")
        print("\nNext steps:")
        print("  1. Run the example: python sre_agent_example.py")
        print("  2. Read the guide: AGENT_SDK_GUIDE.md")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please address the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
