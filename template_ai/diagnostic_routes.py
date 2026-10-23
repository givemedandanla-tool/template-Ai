"""UI-066 reuses the actual existing diagnostics; no independent report format is inferred."""
ROUTES={'input':'OUTPUT_INPUT_PROBLEMS','candidate':'OUTPUT_CURRENT_ISSUES','training':'EXISTING_TRAINING_QUALITY'}

def open_diagnostic(window,kind):
    if kind not in ROUTES:raise ValueError('獨立報告格式／交接未定，沒有此路由')
    if kind=='training':window.training_center()
    else:
        window.tabs.setCurrentIndex(2)
        if kind=='input':window.refresh_input_problems();window.input_problems.setFocus()
        else:
            row=window.candidate_list.currentRow()
            if row<0:raise ValueError('先選取現有候選；不產生第二套診斷')
            window.choose_candidate(row);window.issues.setFocus()
    return ROUTES[kind]
