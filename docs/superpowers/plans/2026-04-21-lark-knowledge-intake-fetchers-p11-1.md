# Lark Knowledge Intake Fetchers P11.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the P11.1 fetchers foundation for `lark-knowledge-intake` so URLs and file paths can be classified into `source_type` values and routed through a stable `FetchResult` contract without fetching content yet.

**Architecture:** Add an internal `fetchers/` package under the intake skill. `dispatcher.py` owns source detection and failure-state dispatch, `types.py` defines the shared result contract, and `credentials.py` centralizes `.local` lookups. Config and skill docs are extended without changing current intake behavior.

**Tech Stack:** Python standard library, `pytest`, Markdown docs, JSON config

---

### Task 1: Map Files And Extend Configuration

**Files:**
- Create: `skills/lark-knowledge-intake/fetchers/README.md`
- Modify: `skills/lark-knowledge-intake/SKILL.md`
- Modify: `skills/lark-knowledge-config/config.json`
- Modify: `.gitignore`

- [ ] **Step 1: Update config with the full `source_type_options` enum**

```json
"source_type_options": [
  "article",
  "paywall_news",
  "wechat_mp",
  "tweet",
  "zhihu",
  "xhs_note",
  "video_bilibili",
  "video_youtube",
  "podcast",
  "doc_pdf",
  "doc_docx",
  "doc_pptx",
  "doc_xlsx",
  "doc_epub",
  "arxiv",
  "image",
  "fallback",
  "fetch_failed"
]
```

- [ ] **Step 2: Document the internal fetchers routing behavior in the intake skill**

```md
### 多源抓取器（fetchers）

intake 内部增加 `fetchers/` 子模块后，系统会先按 URL 或文件路径自动识别 `source_type`，再路由到对应 fetcher。

- 文件优先按扩展名识别
- URL 再按已知域名识别
- 无法命中时走 `fallback`
- 对应 fetcher 全部失败时可标记为 `fetch_failed`

P11.1 阶段只完成识别与统一返回契约，不改变现有对外工作流。
```

- [ ] **Step 3: Document `.local` credential storage and ignore it from git**

```gitignore
skills/lark-knowledge-intake/.local/
```

### Task 2: Write Dispatcher Tests First

**Files:**
- Create: `skills/lark-knowledge-intake/fetchers/tests/test_dispatcher.py`

- [ ] **Step 1: Write failing tests for source detection**

```python
import pytest

from skills.lark-knowledge-intake.fetchers.dispatcher import detect_source_type, dispatch


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://example.com/post", "fallback"),
        ("https://mp.weixin.qq.com/s/abc", "wechat_mp"),
        ("https://x.com/user/status/1", "tweet"),
        ("/tmp/file.pdf", "doc_pdf"),
    ],
)
def test_detect_source_type(value, expected):
    assert detect_source_type(value) == expected
```

- [ ] **Step 2: Run tests to verify import or assertion failure**

Run: `pytest skills/lark-knowledge-intake/fetchers/tests/test_dispatcher.py -q`
Expected: FAIL because fetchers module does not exist yet

- [ ] **Step 3: Add failing tests for dispatch contract**

```python
def test_dispatch_returns_failed_fetch_result():
    result = dispatch("https://x.com/user/status/1")

    assert result.success is False
    assert result.source_type == "tweet"
    assert result.url_or_path == "https://x.com/user/status/1"
    assert result.markdown is None
    assert result.error is not None
```

### Task 3: Implement Minimal Fetchers Package

**Files:**
- Create: `skills/lark-knowledge-intake/fetchers/__init__.py`
- Create: `skills/lark-knowledge-intake/fetchers/types.py`
- Create: `skills/lark-knowledge-intake/fetchers/credentials.py`
- Create: `skills/lark-knowledge-intake/fetchers/dispatcher.py`

- [ ] **Step 1: Define the shared `FetchResult` dataclass**

```python
@dataclass(slots=True)
class FetchResult:
    markdown: str | None
    title: str | None
    meta: dict[str, Any]
    source_type: str
    url_or_path: str
    success: bool
    error: str | None
```

- [ ] **Step 2: Implement `.local` credential loading**

```python
def load_local_credential(name: str) -> str | None:
    ...
```

- [ ] **Step 3: Implement detection and failure dispatch**

```python
def detect_source_type(url_or_path: str) -> str:
    ...


def dispatch(url_or_path: str) -> FetchResult:
    ...
```

- [ ] **Step 4: Re-run tests and make them pass**

Run: `pytest skills/lark-knowledge-intake/fetchers/tests/test_dispatcher.py -q`
Expected: PASS

### Task 4: Verify End-To-End P11.1 Acceptance

**Files:**
- Reuse: `skills/lark-knowledge-intake/fetchers/tests/test_dispatcher.py`
- Reuse: `skills/lark-knowledge-config/config.json`

- [ ] **Step 1: Run the targeted test suite**

Run: `pytest skills/lark-knowledge-intake/fetchers/tests/test_dispatcher.py -q`
Expected: all tests pass

- [ ] **Step 2: Run an additional source detection sanity check**

Run:

```bash
python3 - <<'PY'
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

path = Path("skills/lark-knowledge-intake/fetchers/dispatcher.py").resolve()
spec = spec_from_file_location("lk_dispatcher", path)
module = module_from_spec(spec)
spec.loader.exec_module(module)

samples = [
    "https://mp.weixin.qq.com/s/abc",
    "https://www.nytimes.com/2026/04/21/example.html",
    "https://arxiv.org/abs/1234.5678",
    "/tmp/demo.pdf",
]
for item in samples:
    print(item, "=>", module.detect_source_type(item))
PY
```

Expected: prints the mapped `source_type` values without exceptions
