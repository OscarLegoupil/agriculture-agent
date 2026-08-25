from kaggle_environments import make


def test_env_is_registered() -> None:
    env = make("kaggriculture")
    assert env.specification.name == "kaggriculture"
    assert env.configuration.episodeSteps == 720


def test_full_episode_terminates_with_valid_rewards() -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 42})
    env.run(["pass", "random"])

    final = env.steps[-1]
    assert len(final) == 2
    assert all(s.status == "DONE" for s in final)
    for s in final:
        assert isinstance(s.reward, (int, float))
        assert s.reward >= 0


def test_seeded_episode_is_deterministic() -> None:
    def run_once() -> tuple[float, float]:
        env = make("kaggriculture", configuration={"episodeSteps": 240, "seed": 123})
        env.run(["pass", "starter"])
        final = env.steps[-1]
        return float(final[0].reward), float(final[1].reward)

    assert run_once() == run_once()
