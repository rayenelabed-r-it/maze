from mazes.cli import main


def test_list(capsys):
    assert main(["list"]) == 0
    sortie = capsys.readouterr().out
    assert "kruskal" in sortie and "astar" in sortie


def test_generate_puis_solve(tmp_path, capsys):
    fichier = tmp_path / "maze.txt"
    assert main(["generate", "--n", "10", "--seed", "1", "--check",
                 "--output", str(fichier)]) == 0
    assert fichier.exists()

    resolu = tmp_path / "solved.txt"
    assert main(["solve", "--input", str(fichier), "--algorithm", "astar",
                 "--output", str(resolu)]) == 0
    assert "o" in resolu.read_text(encoding="utf-8")
