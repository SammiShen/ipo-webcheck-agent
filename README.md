# IPO WebCheck Agent

> AI-powered workflow automation for IPO legal due diligence.
>
> 面向 IPO 法律尽职调查场景的 AI 工作流自动化工具。

---

# 🇬🇧 English

## Overview

IPO WebCheck Agent is an AI-powered workflow automation tool designed for IPO legal due diligence.

It automates repetitive web verification tasks, including judicial document search, enforcement information retrieval, ICP record lookup, screenshot capture, report generation, and AI-generated execution summaries.

The project focuses on improving workflow efficiency rather than replacing legal professionals.

---

## Motivation

During IPO due diligence, legal professionals often spend considerable time performing repetitive web verification for multiple companies.

Typical tasks include:

* Searching judicial documents
* Checking enforcement records
* Verifying ICP registration
* Capturing screenshots
* Recording search results
* Organizing reports

These tasks are repetitive and time-consuming.

This project was developed to automate the workflow while keeping legal review under human supervision.

---

## Features

* Batch company search
* Judicial document search
* Enforcement information search
* CAC search
* MIIT ICP search
* Automatic screenshot capture
* Excel report generation
* AI-generated execution summary
* Gradio graphical interface

---

## Tech Stack

* Python
* Playwright
* Gradio
* Qwen API
* OpenAI SDK

---

## Project Structure

```text
ipo-webcheck-agent/

├── app.py
├── config.py
├── requirements.txt
├── runners/
└── utils/
```

---

## Workflow

1. Input company names
2. Launch browser automation
3. Search official websites
4. Capture screenshots automatically
5. Generate Excel reports
6. Generate AI execution summary

---

## Future Plans

* Support more official websites
* OCR integration
* Smarter report generation
* Docker deployment
* Cross-platform support

---

## Disclaimer

This project is designed for workflow automation only.

It does **not** provide legal advice or legal opinions.

Users remain responsible for reviewing all search results and making legal judgments.

---

# 🇨🇳 中文介绍

## 项目简介

IPO WebCheck Agent 是一个面向 IPO 法律尽职调查场景开发的 AI 工作流自动化工具。

项目通过浏览器自动化与大模型能力，实现企业网络核查流程自动化，包括司法文书检索、执行信息查询、ICP备案查询、截图留存、检索记录生成以及 AI 运行总结生成等功能。

项目定位为**辅助律师提高工作效率**，而非替代律师进行法律判断。

---

## 开发背景

在 IPO 尽职调查过程中，律师需要对大量企业进行网络核查。

这一流程通常包括：

* 裁判文书网检索
* 中国执行信息公开网检索
* 国家网信办信息检索
* 工信部 ICP 备案查询
* 检索截图留存
* 检索记录整理

上述工作重复性高、耗时长，且容易产生机械性劳动。

因此，本项目尝试利用 AI 与浏览器自动化技术，将重复工作自动化，让法律专业人员能够将更多精力投入法律分析与专业判断。

---

## 主要功能

* 企业名称批量输入
* 裁判文书网自动检索
* 中国执行信息公开网自动检索
* 国家网信办自动检索
* 工信部 ICP 自动检索
* 自动截图
* 自动生成 Excel 检索记录
* AI 自动生成运行总结
* Gradio 图形界面

---

## 技术栈

* Python
* Playwright
* Gradio
* Qwen API
* OpenAI SDK

---

## 项目目标

利用 AI 与浏览器自动化技术，减少 IPO 网络核查过程中的重复劳动，提高法律工作流程效率。

项目重点在于**工作流自动化（Workflow Automation）**，而非法律意见生成。

---

## 后续计划

* 支持更多官方网站
* OCR 自动识别
* 更智能的报告生成
* Docker 部署
* 跨平台支持

---

## 免责声明

本项目仅用于工作流程自动化。

项目不提供法律意见或法律建议，所有检索结果均需由法律专业人员进行审核并作出判断。
