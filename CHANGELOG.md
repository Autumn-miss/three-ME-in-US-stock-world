# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), adapted for a fast-moving local-first simulation project.

## [0.2.0] - 2026-06-19

### Added

- English, bilingual, and Chinese dashboard display modes
- English README screenshots for strategy, returns, holdings, and orders
- MIT license for the public repository
- Reusable screenshot capture script for README assets
- `CHANGELOG.md` for visible project progress tracking
- Share-friendly repository cover artwork

### Changed

- README expanded with Features, workflow explanations, screenshots, and contributor-facing project context
- Dashboard navigation, high-level labels, persona names, and style names translated into English
- Orders, trades, and strategy headers translated into English
- Strategy body cells and order reasons can now be shown in bilingual `EN / ZH` format
- Startup launcher renamed to `Start Virtual US Stock World.command`

### Fixed

- Daily run behavior now catches up missing trading days instead of stopping at the last partially updated date
- Strategy page now focuses on the latest 5 trading days and collapses older history into expandable windows
- Startup script path handling is now portable instead of machine-specific

## [0.1.0] - 2026-06-18

### Added

- Initial public GitHub release of the virtual US stock simulation project
- Streamlit dashboard for portfolio snapshots, returns, holdings, orders, and strategy output
- Yahoo Finance daily market-data workflow
- Three simulated investing personas with separate order-generation logic
- SQLite-backed local project data model

[0.2.0]: https://github.com/Autumn-miss/three-ME-in-US-stock-world/compare/02fcd8e...HEAD
[0.1.0]: https://github.com/Autumn-miss/three-ME-in-US-stock-world/commit/02fcd8e
