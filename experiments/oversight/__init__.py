"""実証実験: 監督のスケーリング（oversight scaling）。

governance.py が *仮定* していた oversight_error（人間/弱い監督が高リスク誤りを見逃す率）を、
実モデルで **実測** する。弱い監督者に、巧妙さの異なる仕込み欠陥を含む成果物をレビューさせ、
欠陥の巧妙さ × 監督者の能力 に対する捕捉率の崩れを測る。

これは「統治膜の破綻点」(foundations §5 / AI-2027 の核) の crux を、トイモデルから
実証へ接地する一手。決定的 mock backend で harness を検証し、ollama で実測する。
"""
