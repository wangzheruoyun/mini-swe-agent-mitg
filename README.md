<div align="center">
<a href="https://mini-swe-agent.com/latest/"><img src="https://github.com/SWE-agent/mini-swe-agent/raw/main/docs/assets/mini-swe-agent-banner.svg" alt="mini-swe-agent banner" style="height: 7em"/></a>
</div>

# 极简 AI 软件工程智能体 — **mitg** 版 / The minimal AI software engineering agent — **mitg** edition

> [!NOTE]
> 本仓库是 upstream [SWE-agent/mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) 的维护型分支（fork），在保留上游 v2 核心设计的前提下，叠加了一套面向日常使用的增强。**未被标记为 [mitg] 的内容均继承自上游。**
>
> This repository is a maintained fork of upstream [SWE-agent/mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent). It layers a set of everyday-use improvements on top of upstream v2 without changing its core design. Anything **not** explicitly marked **[mitg]** is inherited from upstream.

📣 [mini-swe-agent now powers Ramp SWE-Bench](https://labs.ramp.com/swebench)<br/>
📣 [mini-swe-agent beats Claude Code and Codex on DeepSWE](https://deepswe.datacurve.ai/blog#evaluation-harness)<br/>
📣 [Run mini-swe-agent on our new & extremely challenging benchmark, ProgramBench](https://mini-swe-agent.com/latest/usage/programbench/)<br/>
📣 **[mitg] 新增：中文界面、会话续跑、撤回 (/undo)、动态 `.env`、主副 key、LiteLLM 启动加速。/ [mitg] adds Chinese UI, session resume, `/undo`, dynamic `.env`, primary/fallback keys, faster startup.**

[![Docs](https://img.shields.io/badge/Docs-green?style=for-the-badge&logo=materialformkdocs&logoColor=white)](https://mini-swe-agent.com/latest/)
[![Slack](https://img.shields.io/badge/Slack-4A154B?style=for-the-badge&logo=slack&logoColor=white)](https://join.slack.com/t/swe-bench/shared_invite/zt-36pj9bu5s-o3_yXPZbaH2wVnxnss1EkQ)
[![PyPI - Version](https://img.shields.io/pypi/v/mini-swe-agent?style=for-the-badge&logo=python&logoColor=white&labelColor=black&color=deeppink)](https://pypi.org/project/mini-swe-agent/)

---

## 中文简介 / Chinese overview

2024 年，我们构建了 [SWE-bench](https://github.com/swe-bench/SWE-bench) 与 [SWE-agent](https://github.com/swe-agent/swe-agent)，并推动了编程智能体（coding agent）浪潮的兴起。

现在我们问：**如果我们的智能体简单 100 倍，却依然表现近乎一样好呢？**

`mini` 具备以下特点：

- **被广泛采用**：已被 Meta、NVIDIA、Essential AI、IBM、Nelius、Anyscale、普林斯顿大学、斯坦福大学等使用。
- **极简**：智能体核心类仅约 100 行 Python（[agent 类](https://github.com/SWE-agent/mini-swe-agent/blob/main/src/minisweagent/agents/default.py)，外加少量 [环境](https://github.com/SWE-agent/mini-swe-agent/blob/main/src/minisweagent/environments/local.py)、[模型](https://github.com/SWE-agent/mini-swe-agent/blob/main/src/minisweagent/models/litellm_model.py) 与 [运行脚本](https://github.com/SWE-agent/mini-swe-agent/blob/main/src/minisweagent/run/hello_world.py)）—— 没有花哨的依赖！
- **高性能**：在 [SWE-bench verified](https://www.swebench.com/) 上得分 >74%；启动比 Claude Code 快得多。
- **可部署**：支持 **本地环境**、**docker/podman**、**singularity/apptainer**、**bubblewrap**、**contree** 等。
- **兼容性强**：通过 **litellm**、**openrouter**、**portkey** 等支持几乎所有模型，并兼容 `/completion` 与 `/response` 端点、交错思考等。
- 由 [SWE-bench](https://swebench.com)、[SWE-agent](https://swe-agent.com) 背后的普林斯顿 & 斯坦福团队打造。
- **经过测试**：[![Codecov](https://img.shields.io/codecov/c/github/swe-agent/mini-swe-agent?style=flat-square)](https://codecov.io/gh/SWE-agent/mini-swe-agent)

### [mitg] 本分支新增了什么？ / What's new in this fork?

`mitg` 分支在原有体系无明显问题的地方保持不变，仅在缺失处补充了日常使用所需的系统，且均做到最小改动、相互隔离：

- **国际化（i18n）**：零依赖的 JSON 目录方案（`minisweagent/i18n`）。启动时自动检测系统语言；默认随附中文（`zh`）目录，英文源字符串作为回退。所有面向用户的文案（横幅、提示、确认、帮助）均已本地化。
- **`/undo` 撤回**：新增 `UndoRequested` 异常，可撤销最近一次已执行的步骤（含其计费与成本统计）并重新提示，无需重跑整个任务。
- **会话续跑**：未显式指定任务启动时，CLI 会直接从上次未完成任务对应的轨迹文件（`last_mini_run.traj.json`）恢复——检测到轨迹文件后会**询问是否加载**；确认后完整对话上下文得以保留，直接回到上次退出时的状态继续。
- **动态 `.env` 与主副 key（运行时故障转移）**：每次启动重新加载全局配置（`.env` 的改动会在下次运行生效）；并支持**主副 key**——当主 key 被限速或不可达时，自动切换到 `*_FALLBACK` 备用 key 重试。启动时打印当前生效的 key 值（模型名完整显示，密钥脱敏）。
- **更快启动 + 实时进度条**：以往 LiteLLM 会在模块加载时被间接导入（约 10 秒无声卡顿，UI 才出现）。现已改为首次使用时懒加载，模块导入降至约 1.3 秒；并且 `mini` 一启动就显示真实百分比进度条，启动过程不再像卡死。
- 版本号提升为 **`2.4.6+mitg`**。

#### 使用副 key（主副 key） / Using a fallback (secondary) key

本分支支持**主副 key（运行时故障转移）**：主 key（或模型名）在启动前为空时会自动使用 `*_FALLBACK`；更重要的是，在运行期间若主 key 被**限速（RateLimit）或不可达（连接/服务错误）**，会自动切换到备用 key 并重试，无需手动干预。启动时也会打印当前实际生效的 key 值（模型名完整显示，密钥脱敏）。

在全局配置文件（`~/.config/mini-swe-agent/.env`）或环境变量中设置即可：

```bash
# 主 key（优先使用）/ Primary key (used first)
MSWEA_MODEL_NAME=openai/gpt-5.4
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx

# 副 key（主 key 为空时自动回退；运行中被限速/不可达时也会自动切换）/ Fallback key
MSWEA_MODEL_NAME_FALLBACK=anthropic/claude-opus-4-6
OPENAI_API_KEY_FALLBACK=sk-yyyyyyyyyyyyyyyy
```

启动后你会看到类似输出：

```text
主密钥（MSWEA_MODEL_NAME）= openai/gpt-5.4。
主密钥（OPENAI_API_KEY）= sk-3…5bc7。
```

也可以仅在需要时用环境变量临时切换：`export MSWEA_MODEL_NAME_FALLBACK=...`。

### 快速开始 / Getting started

本项目推荐使用系统已有的 **uv** 从源码安装（开发者模式）：

```bash
# 1. 克隆仓库 / Clone the repository
git clone https://github.com/wangzheruoyun/mini-swe-agent-mitg.git
cd mini-swe-agent-mitg

# 2. 使用 uv 安装（可编辑模式）/ Install with uv (editable)
uv pip install -e .

# 3. 运行 CLI / Run the CLI
mini
```

> 也可使用 `uv tool install . --force` 将其安装为独立工具，或参考上游文档用 `pip` 安装发布版。
> You may also use `uv tool install . --force` to install it as a standalone tool, or install the published package via `pip` following the upstream docs.

更多用法请参阅 [官方文档](https://mini-swe-agent.com/latest/)：

* [快速开始](https://mini-swe-agent.com/latest/quickstart/)
* [使用 `mini` CLI](https://mini-swe-agent.com/latest/usage/mini/)
* [全局配置](https://mini-swe-agent.com/latest/advanced/global_configuration/)
* [YAML 配置文件](https://mini-swe-agent.com/latest/advanced/yaml_configuration/)
* [Cookbook 进阶](https://mini-swe-agent.com/latest/advanced/cookbook/)
* [常见问题](https://mini-swe-agent.com/latest/faq/)
* [参与贡献](https://mini-swe-agent.com/latest/contributing/)

---

## English overview

In 2024, we built [SWE-bench](https://github.com/swe-bench/SWE-bench) & [SWE-agent](https://github.com/swe-agent/swe-agent) and helped kickstart the coding agent revolution.

We now ask: **What if our agent was 100x simpler, and still worked nearly as well?**

`mini` is

- **Widely adopted**: Used by Meta, NVIDIA, Essential AI, IBM, Nebius, Anyscale, Princeton University, Stanford University, and many more.
- **Minimal**: Just some 100 lines of python for the [agent class](https://github.com/SWE-agent/mini-swe-agent/blob/main/src/minisweagent/agents/default.py) (and a bit more for the [environment](https://github.com/SWE-agent/mini-swe-agent/blob/main/src/minisweagent/environments/local.py), [model](https://github.com/SWE-agent/mini-swe-agent/blob/main/src/minisweagent/models/litellm_model.py), and [run script](https://github.com/SWE-agent/mini-swe-agent/blob/main/src/minisweagent/run/hello_world.py)) — no fancy dependencies!
- **Performant:** Scores >74% on the [SWE-bench verified benchmark](https://www.swebench.com/); starts much faster than Claude Code.
- **Deployable:** Supports **local environments**, **docker/podman**, **singularity/apptainer**, **bubblewrap**, **contree**, and more.
- **Compatible:** Supports all models via **litellm**, **openrouter**, **portkey**, and more. Support for `/completion` and `/response` endpoints, interleaved thinking etc.
- Built by the Princeton & Stanford team behind [SWE-bench](https://swebench.com), [SWE-agent](https://swe-agent.com), and more.
- **Tested:** [![Codecov](https://img.shields.io/codecov/c/github/swe-agent/mini-swe-agent?style=flat-square)](https://codecov.io/gh/SWE-agent/mini-swe-agent)

### [mitg] What's new in this fork?

The `mitg` fork keeps the upstream agent untouched where it already works, and adds the systems that were missing for everyday use. Each addition is minimal and isolated:

- **Internationalization (i18n).** A zero-dependency JSON-catalog system (`minisweagent/i18n`). The CLI detects the system language on startup; a Chinese (`zh`) catalog ships by default, and English strings are used verbatim as the fallback. All user-facing text (banners, prompts, confirmations, help) is localized.
- **`/undo` — revert the last action.** A new `UndoRequested` exception lets you undo the most recently executed step (including its accounting) and re-prompt, instead of redoing the whole run.
- **Session resume.** On launch without an explicit task, the CLI restores the last *unfinished* run directly from its trajectory file (`last_mini_run.traj.json`) — when a trajectory file is detected you are **asked whether to load it**; on confirmation the full conversation context is preserved, so you continue exactly where you left off.
- **Dynamic `.env` + primary/fallback keys (runtime failover).** The global config (`.env`) is re-loaded on every launch so edits take effect on the next run, and a **primary/fallback key** setup is supported: if the primary key is rate-limited or unreachable, the agent automatically switches to the `*_FALLBACK` key and retries. Startup prints the active key values (model names in full; secrets masked).
- **Faster startup & a live progress bar.** LiteLLM used to be imported transitively at module load (~10 s of silent freeze before any UI appeared). It is now imported lazily (first use), cutting module-import time to ~1.3 s, and a real percentage progress bar is shown the instant `mini` launches so startup never looks frozen.
- Version is bumped to **`2.4.6+mitg`**.

#### Using a fallback (secondary) key

This fork supports a **primary/fallback (secondary) key** setup. If the primary key (or model name) is empty at startup it automatically uses the `*_FALLBACK` value; more importantly, during a run, if the primary key is **rate-limited or unreachable** (connection/service errors), the agent automatically switches to the fallback key and retries — no manual intervention needed. The active key values are also printed at startup (model names shown in full, secrets masked).

Set them in the global config file (`~/.config/mini-swe-agent/.env`) or as environment variables:

```bash
# Primary key (used first)
MSWEA_MODEL_NAME=openai/gpt-5.4
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx

# Fallback key (auto-used if primary empty, or on rate-limit/unreachable at runtime)
MSWEA_MODEL_NAME_FALLBACK=anthropic/claude-opus-4-6
OPENAI_API_KEY_FALLBACK=sk-yyyyyyyyyyyyyyyy
```

At startup you'll see something like:

```text
Primary key (MSWEA_MODEL_NAME) = openai/gpt-5.4.
Primary key (OPENAI_API_KEY) = sk-3…5bc7.
```

You can also switch temporarily with `export MSWEA_MODEL_NAME_FALLBACK=...`.

### Getting started

We recommend installing from source with the system **uv** tool (developer mode):

```bash
# 1. Clone the repository
git clone https://github.com/wangzheruoyun/mini-swe-agent-mitg.git
cd mini-swe-agent-mitg

# 2. Create a virtual environment and install (editable)
uv venv                 # create ./venv (once)
source venv/bin/activate
uv pip install -e .

# 3. Run the CLI
mini
```

- `uv pip install -e .` requires an active virtual environment (or pass `--system` to install into the system Python). The `uv venv` step above is mandatory.
- You may instead use `uv tool install . --force` to install `mini` as a standalone, isolated tool (this is *not* editable — reinstall after code changes). See the upstream docs for installing a published wheel via `pip`.

Read more in our [documentation](https://mini-swe-agent.com/latest/):

* [Quick start guide](https://mini-swe-agent.com/latest/quickstart/)
* [Using the `mini` CLI](https://mini-swe-agent.com/latest/usage/mini/)
* [Global configuration](https://mini-swe-agent.com/latest/advanced/global_configuration/)
* [Yaml configuration files](https://mini-swe-agent.com/latest/advanced/yaml_configuration/)
* [Power up with the cookbook](https://mini-swe-agent.com/latest/advanced/cookbook/)
* [FAQ](https://mini-swe-agent.com/latest/faq/)
* [Contribute!](https://mini-swe-agent.com/latest/contributing/)

---

## Attribution

If you found this work helpful, please consider citing the [SWE-agent paper](https://arxiv.org/abs/2405.15793) in your work:

```bibtex
@inproceedings{yang2024sweagent,
  title={{SWE}-agent: Agent-Computer Interfaces Enable Automated Software Engineering},
  author={John Yang and Carlos E Jimenez and Alexander Wettig and Kilian Lieret and Shunyu Yao and Karthik R Narasimhan and Ofir Press},
  booktitle={The Thirty-eighth Annual Conference on Neural Information Processing Systems},
  year={2024},
  url={https://arxiv.org/abs/2405.15793}
}
```

Our other projects:

<div align="center">
  <a href="https://github.com/SWE-agent/SWE-agent"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/sweagent_logo_text_below.svg" alt="SWE-agent" height="120px"></a>
   &nbsp;&nbsp;
  <a href="https://github.com/SWE-agent/SWE-ReX"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/swerex_logo_text_below.svg" alt="SWE-ReX" height="120px"></a>
   &nbsp;&nbsp;
  <a href="https://github.com/SWE-bench/SWE-bench"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/swebench_logo_text_below.svg" alt="SWE-bench" height="120px"></a>
   &nbsp;&nbsp;
  <a href="https://github.com/SWE-bench/SWE-smith"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/swesmith_logo_text_below.svg" alt="SWE-smith" height="120px"></a>
   &nbsp;&nbsp;
  <a href="https://github.com/codeclash-ai/codeclash"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/codeclash_logo_text_below.svg" alt="CodeClash" height="120px"></a>
   &nbsp;&nbsp;
  <a href="https://github.com/SWE-bench/sb-cli"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/sbcli_logo_text_below.svg" alt="sb-cli" height="120px"></a>
</div>
