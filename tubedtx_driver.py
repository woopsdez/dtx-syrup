"""TubeDTX の venv で実行する小さなドライバ。cwd は TubeDTX のフォルダ（config.json を読み書きするため）。

usage: python tubedtx_driver.py <YouTube URL> [--dry-run]
stdout に PROJECT_PATH=<曲フォルダ> と RESULT=ok|fail を出す。
"""
import multiprocessing as mp
import os
import sys


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else ''
    dry_run = '--dry-run' in sys.argv
    sys.path.insert(0, os.getcwd())
    from scripts import gradio_utils as g  # Gradio 本体も import されるが UI は起動しない

    cfg = g.app_config
    print(f'WORKSPACE={cfg.workspace_path}', flush=True)
    if dry_run:
        print('DRY_RUN url=' + url, flush=True)
        print('RESULT=ok', flush=True)
        return 0
    if not url:
        print('URL がありません')
        print('RESULT=fail', flush=True)
        return 1

    out = g.new_score_gr(url)          # [log, project_path, preimage, *config]
    project_path = out[1]
    print(f'PROJECT_PATH={project_path}', flush=True)
    print(out[0], flush=True)

    res = g._batch_convert_gr(mp.Lock(), project_path)  # noqa: SLF001 - download → separate → midi → dtx
    print(res[0], flush=True)
    print(res[1], flush=True)
    config = g.ProjectConfig.load(project_path)
    ok = '[失敗]' not in res[1] and os.path.exists(os.path.join(project_path, config.dtx_output_name))
    print('RESULT=' + ('ok' if ok else 'fail'), flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
