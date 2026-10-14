from lora_dev.__main__ import main


def test_cli_requires_request(monkeypatch):
    monkeypatch.setattr("sys.argv", ["lora_dev"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 2
