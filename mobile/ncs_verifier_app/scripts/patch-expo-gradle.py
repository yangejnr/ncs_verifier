#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE_MODULES = ROOT / "node_modules"


def _guard_after_evaluate(text: str) -> str:
    result: list[str] = []
    i = 0
    while True:
        start = text.find("afterEvaluate", i)
        if start == -1:
            result.append(text[i:])
            break
        result.append(text[i:start])
        brace_start = text.find("{", start)
        if brace_start == -1:
            result.append(text[start:])
            break
        depth = 0
        end = None
        for j in range(brace_start, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end is None:
            result.append(text[start:])
            break
        block = text[start : end + 1]
        if "components.release" in block and "components.findByName(\"release\")" not in block:
            lines = block.splitlines()
            for idx, line in enumerate(lines):
                if "afterEvaluate" in line:
                    indent = line.split("afterEvaluate")[0]
                    guard_indent = indent + "  "
                    lines.insert(idx + 1, f"{guard_indent}if (components.findByName(\"release\") != null) {{")
                    for j in range(len(lines) - 1, -1, -1):
                        if lines[j].strip() == "}":
                            lines.insert(j, f"{guard_indent}}}")
                            break
                    block = "\n".join(lines)
                    break
        result.append(block)
        i = end + 1
    return "".join(result)


def patch_build_gradle(path: Path) -> bool:
    text = path.read_text()
    original = text
    text = text.replace("classifier = 'sources'", "archiveClassifier.set('sources')")
    text = _guard_after_evaluate(text)
    if text != original:
        path.write_text(text)
        return True
    return False


def main() -> None:
    if not NODE_MODULES.exists():
        print("node_modules not found; skip patching")
        return

    patched = 0
    for path in NODE_MODULES.glob("expo-*/android/build.gradle"):
        if patch_build_gradle(path):
            patched += 1

    plugin_path = NODE_MODULES / "expo-modules-core" / "android" / "ExpoModulesCorePlugin.gradle"
    if plugin_path.exists():
        text = plugin_path.read_text()
        original = text
        text = text.replace(
            "if (project.plugins.hasPlugin('kotlin-android')) {",
            "if (project.plugins.hasPlugin('kotlin-android') && project.extensions.findByName(\"android\") != null) {",
        )
        if "components.findByName(\"release\")" not in text:
            text = text.replace(
                "afterEvaluate {\n    publishing {",
                "afterEvaluate {\n    if (components.findByName(\"release\") != null) {\n      publishing {",
            )
            text = text.replace("\n  }\n}", "\n    }\n  }\n}")
        if text != original:
            plugin_path.write_text(text)
            patched += 1

    print(f"Patched Expo Gradle files: {patched}")


if __name__ == "__main__":
    main()
