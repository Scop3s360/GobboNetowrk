# Project Codename: GoblinOS

**Version:** 1.0 Canonical Development Guide

---

# Vision

GoblinOS is an operating system for AI workers.

Rather than creating one AI that attempts to perform every task, GoblinOS manages a collection of specialist AI agents, each with a clearly defined responsibility.

The Director Agent receives requests from the user, decides which specialist agents are required, delegates work, gathers the results and presents a final response.

The system should feel like managing a small company rather than chatting with a single assistant.

---

# Core Philosophy

The following principles are absolute.

## Rule 1 - Simplicity First

If there is a simple solution and a complex solution, choose the simple solution.

Do not optimise for problems that do not yet exist.

---

## Rule 2 - Build Only What Is Needed

No feature should exist because it "might be useful later."

Every feature must solve an existing problem.

---

## Rule 3 - One Responsibility Per Agent

Each AI agent has exactly one purpose.

Examples:

Developer
Researcher
Reviewer
Writer

Not:

Developer + Researcher + Artist + QA

---

## Rule 4 - Modular Everything

Every system should be replaceable without affecting the others.

Changing one agent should never require rewriting the entire application.

---

## Rule 5 - Human Always In Control

Agents never perform destructive actions automatically.

The user approves important actions.

---

# Version 1 Goal

Version 1 has one objective:

**Prove that multiple AI agents can successfully work together on a single task.**

Nothing more.

Do not attempt to build AGI.

Do not attempt to automate entire businesses.

Do not add unnecessary intelligence.

---

# Technology Stack

Language

Python

Reason:
Simple
Large ecosystem
Excellent AI libraries

---

Backend

FastAPI

Reason:
Lightweight
Modern
Easy to expand

---

Database

SQLite

Reason:
No server required.
Upgrade to PostgreSQL later if necessary.

---

Frontend

React + Electron

Reason:
Cross-platform desktop application.

Initially a very simple interface.

---

Model

OpenAI Responses API

The model provider should be abstracted so another provider can be substituted later.

---

# Folder Structure

The project should remain organised from day one.

```text
GoblinOS/

agents/
director/
developer/
researcher/
reviewer/

tools/
memory/
database/
api/
frontend/
config/
logs/
docs/
tests/
```

No large files.

No "misc" folder.

No duplicated code.

---

# Development Phases

## Phase 1 - Foundation

Objective

Create the basic application.

Deliverables

Python project

Configuration system

OpenAI connection

Logging

Basic desktop window

Settings screen

Success Criteria

Application launches.

Can communicate with the AI.

Nothing else.

---

## Phase 2 - Single Agent

Objective

Create one working AI agent.

Agent

Research Agent

Capabilities

Receive prompt

Return response

No memory

No tools

Success Criteria

User types question.

Research Agent answers.

---

## Phase 3 - Tool System

Objective

Allow agents to perform actions.

Create a generic Tool interface.

Every tool should follow the same structure.

Example tools

Read File

Write File

Search Web

Read Folder

List Directory

Run Command

Success Criteria

Research Agent successfully calls a tool.

---

## Phase 4 - Memory

Objective

Allow persistent memory.

Memory Types

Conversation Memory

Project Memory

Agent Memory

Memory should be stored outside the model.

The model never owns memory.

Success Criteria

Restart application.

Agent remembers previous information.

---

## Phase 5 - Director Agent

Objective

Introduce orchestration.

Responsibilities

Read user request

Determine required agent

Delegate work

Receive results

Return final response

Initially the Director should only choose ONE specialist.

No parallel execution.

Success Criteria

User never speaks directly to Research Agent.

Director handles everything.

---

## Phase 6 - Second Specialist

Add Developer Agent.

Purpose

Software engineering only.

No research.

No creative writing.

Success Criteria

Director successfully chooses between

Research Agent

Developer Agent

---

## Phase 7 - Third Specialist

Reviewer Agent

Purpose

Critique work.

Identify weaknesses.

Suggest improvements.

Never create new work.

Only review.

---

## Phase 8 - Multi-Agent Workflow

Objective

Agents collaborate.

Example

Director

↓

Developer

↓

Reviewer

↓

Director

↓

User

No agent should directly call another.

All communication passes through the Director.

---

# Initial Agents

Director

Purpose

Task coordination.

---

Researcher

Purpose

Find information.

---

Developer

Purpose

Programming.

---

Reviewer

Purpose

Quality assurance.

---

# Agents That Are Explicitly Out of Scope

Do NOT build these during Version 1.

Marketing

Finance

Artist

Game Designer

Steam Publisher

Social Media

Voice

Vision

Autonomous Internet Browsing

Scheduling

Email

Calendar

Image Generation

These belong in Version 2 or later.

---

# Tool Design

Every tool should expose exactly the same interface.

Example

Tool Name

Description

Input

Output

Error

Permission Level

This makes tools interchangeable.

---

# Memory Design

Memory should be searchable.

Do not reload entire histories.

Future memories should support:

Tags

Projects

Importance

Date

Source

---

# Logging

Every important action should be logged.

Examples

User Prompt

Director Decision

Agent Selected

Tool Used

Time Taken

Errors

These logs are essential for debugging.

---

# Coding Standards

Functions should remain small.

Files should remain under approximately 500 lines where practical.

Classes should have one responsibility.

Avoid global variables.

Use meaningful names.

Write comments explaining why, not what.

---

# UI Philosophy

The interface should remain clean.

Required

Chat

Status

Active Agent

Logs

Settings

Nothing more.

Avoid dashboards.

Avoid dozens of panels.

---

# Definition of Done

A feature is complete only when

It works.

It has been manually tested.

Errors are handled.

Logging exists.

Documentation updated.

---

# Version 1 Completion Criteria

Version 1 is complete when the following workflow succeeds.

User asks a question.

↓

Director analyses request.

↓

Director selects appropriate specialist.

↓

Specialist completes task.

↓

Reviewer critiques result.

↓

Director returns polished answer.

↓

Conversation is stored in memory.

If this workflow functions reliably, Version 1 is considered complete.

Development should stop here before Version 2 begins.

---

# Things We Will Not Do

We will not build AGI.

We will not build self-improving AI.

We will not build autonomous internet agents.

We will not build dozens of agents.

We will not optimise prematurely.

We will not add features without a clear purpose.

We will finish Version 1 before discussing Version 2.

---

# Final Principle

Every new feature must answer one question:

**"Does this help the Director coordinate specialists more effectively?"**

If the answer is no, the feature does not belong in Version 1.
