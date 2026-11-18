# Forward Science

*Essays on the institutions that turn new intelligence into scientific progress.*

Forward Science is a six-part essay collection on AI for science, **forward-deployed scientists**, scientific loops, scientific intermediaries, and the transition toward self-driving laboratories. It examines how research institutions incorporate computational and automated systems into accountable scientific work.

The [concept guide](https://fraware.github.io/forward-science/concepts/) defines the central ideas and links each one to its primary essay. The [corpus index](https://fraware.github.io/forward-science/corpus.json) provides structured reading and citation metadata, and [llms.txt](https://fraware.github.io/forward-science/llms.txt) supplies an agent-oriented reading map. These aids describe the essays; they do not replace the original arguments.

**[Read the essays](https://fraware.github.io/forward-science/)**

---

### The series

1. [Forward Science](https://fraware.github.io/forward-science/forward-science/)
2. [Forward-Deployed Scientists](https://fraware.github.io/forward-science/forward-deployed-scientists/)
3. [The Unit of Deployment Is the Scientific Loop](https://fraware.github.io/forward-science/scientific-loop/)
4. [From Extension Agents to Forward-Deployed Scientists](https://fraware.github.io/forward-science/extension-agents/)
5. [Who Pays for the Scientist Who Makes Other Scientists Better](https://fraware.github.io/forward-science/political-economy/)
6. [Between the Manual Lab and the Self-Driving Lab](https://fraware.github.io/forward-science/future-laboratory/)

Originally published in June 2026 by **[Mateo H. Petel](https://mateopetel.xyz/)** on [Critical Systems](https://mateopetel.substack.com/t/forward-science).

### Run locally

```sh
python -m pip install -r requirements-build.txt
python scripts/build.py --strict
python -m http.server --directory site 8000
```

### License

The website software is [MIT licensed](LICENSE). The essays and original editorial content remain © 2026 Mateo H. Petel, all rights reserved.
