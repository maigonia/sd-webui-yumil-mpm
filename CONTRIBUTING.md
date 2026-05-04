# Contributing to sd-webui-yumil-mpm

Thank you for your interest in contributing.

ご関心ありがとうございます。

This extension is licensed under MIT and welcomes community contributions.

この拡張機能は MIT ライセンスでコミュニティ貢献を歓迎しています。

---

## Target environment / 対象環境

This extension targets **Stable Diffusion WebUI Forge neo**.

本拡張機能は **Stable Diffusion WebUI Forge neo** を対象としています。

---

## Pull Requests / プルリクエスト

We welcome PRs for:

- Bug fixes / バグ修正
- New Settings options / 新規 Settings 項目
- Documentation improvements / ドキュメント改善

For larger changes, please **open an Issue first** to discuss the approach.

大きな変更の場合は、まず Issue で方針を相談してください。

### Workflow / 流れ

1. Fork the repo / リポをフォーク
2. Create a feature branch: `git checkout -b feature/my-change`
3. Make changes and test locally with a real SD WebUI install
4. Push your branch: `git push origin feature/my-change`
5. Open a Pull Request describing your change

ローカルで実機の SD WebUI でテストしてから PR を出してください。

---

## Local testing / ローカルテスト

To test changes:

1. Clone the repo into your SD WebUI's `extensions/` directory:
   ```sh
   cd <SD-WebUI-root>/extensions/
   git clone https://github.com/maigonia/sd-webui-yumil-mpm.git
   ```
2. Restart SD WebUI
3. Verify the extension appears in the Extensions tab and Settings tab
4. Test the integration with Yumil MPM running on `localhost:19720`

---

## Code style / コードスタイル

- Match the existing style of the codebase
- Keep script and parameter names consistent with the existing code
- Comment in English for code, but README / docs can be bilingual

既存コードのスタイルに合わせてください。コード内コメントは英語、README やドキュメントは日英両対応で書いてください。

---

## Issues / Issue 報告

For bug reports and feature requests, see the issue templates available when opening a [new issue](https://github.com/maigonia/sd-webui-yumil-mpm/issues/new/choose).

バグ報告・機能要望は [新規 Issue](https://github.com/maigonia/sd-webui-yumil-mpm/issues/new/choose) のテンプレートをご利用ください。

---

## License / ライセンス

By contributing, you agree that your contributions will be licensed under the MIT License of this repository.

貢献いただいたコードは本リポの MIT ライセンスで公開されることに同意したものとみなします。
