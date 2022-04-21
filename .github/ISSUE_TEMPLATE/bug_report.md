---
name: Bug report
about: Create a report to help us improve
title: ''
labels: ''
assignees: ''

---

#### Prerequisites
Do you want to ask a question? Are you looking for support? The TreeO message board is the best place for getting support: [discussions](https://github.com/envigreen/TreeO/discussions)

* [ ] Put an X between the brackets on this line if you have done all of the following:
    * Checked the FAQs on the message board for common solutions: [FAQ](https://github.com/envigreen/TreeO/discussions/categories/q-a)
    * Checked that your issue isn't already filed: [issues](https://github.com/envigreen/TreeO/issues)

**Versions**
<!-- What version of TreeO are you using? What version of python are you using? -->
| Software | Version |
|----------|---------|
| Python   | 3.8.10  |
| TreeO    | 0.1.0   |

#### Description
<!-- Description of the issue-->

Getting a value from a list inside a dict.

#### Code that produces the error:
Write Python code here that produces the error. Should be a minimal working example (MWE) including example data, see below for an example:

```python
from treeo import TreeO
a = TreeO({"a": 5, "b": [1, 2, 4]})
res = a.b 1
```

#### Expected behavior / result:
What you would expect res to be / to happen. Include data here also if possible.

```python
res = 2
```

#### Actual behavior / result:
What is actually returned / what res actually is. If it results in an error, paste the stack trace or any other information about the error here.

```
Traceback (most recent call last):
  File "/home/lukas/.pyenv/versions/3.6.2/lib/python3.6/code.py", line 64, in runsource
    code = self.compile(source, filename, symbol)
  File "/home/lukas/.pyenv/versions/3.6.2/lib/python3.6/codeop.py", line 168, in __call__
    return _maybe_compile(self.compiler, source, filename, symbol)
  File "/home/lukas/.pyenv/versions/3.6.2/lib/python3.6/codeop.py", line 99, in _maybe_compile
    raise err1
  File "/home/lukas/.pyenv/versions/3.6.2/lib/python3.6/codeop.py", line 87, in _maybe_compile
    code1 = compiler(source + "\n", filename, symbol)
  File "/home/lukas/.pyenv/versions/3.6.2/lib/python3.6/codeop.py", line 133, in __call__
    codeob = compile(source, filename, symbol, self.flags, 1)
  File "<input>", line 1
    a.b 1
        ^
SyntaxError: invalid syntax
```
This is just an example and will actually never work - to get 2 you could e.g. use
```python
a["b 1"]
```

#### Additional Information / Comments:
Any additional information, configuration or data that might be necessary to reproduce the issue. If you have tried different things to mitigate the issue, list them here.
