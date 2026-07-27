import os
import tempfile

from markko_cli import render

SAMPLE = """\
# Title

- [x] done
- [ ] todo

~~strike~~

| a | b |
|---|---|
| 1 | 2 |

```mermaid
graph TD; A-->B;
```
"""


def test_render():
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(SAMPLE)
        path = f.name
    try:
        out = render(path)
        assert "<table>" in out
        assert 'type="checkbox"' in out and "checked" in out
        assert "<del>strike</del>" in out
        assert '<pre class="mermaid">' in out and "graph TD" in out
    finally:
        os.unlink(path)


if __name__ == "__main__":
    test_render()
    print("ok")
