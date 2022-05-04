---
name: Feature request
about: Suggest an idea for this project
title: ''
labels: ''
assignees: ''

---
#### Prerequisites
Do you want to ask a question? Are you looking for support? The Fagus message board is the best place for getting support: [discussions](https://github.com/envigreen/Fagus/discussions)

* [ ] Put an X between the brackets on this line if you have done all of the following:
    * Checked the FAQs on the message board for common solutions: [FAQ](https://github.com/envigreen/Fagus/discussions/categories/q-a)
    * Checked that your issue isn't already filed: [issues](https://github.com/envigreen/Fagus/issues)

#### Is your feature request related to a problem? Please describe.
A clear and concise description of what the problem is. Ex. I'm always frustrated when [...]

#### Describe the solution you'd like
A clear and concise description of what you want to happen. If you could provide example data how that would be helpful (data how it is before and data how the result is).

E.g. I would like Fagus to be able to remove duplicates from a list, like shown below:
```python
from fagus import Fagus
a = Fagus([1, 1, 1, 1, 3, 3, 4, 4, 5, 6])
a.remove_duplicates()
print(a()) # should be [1, 3, 4, 5, 6]
```

#### Describe alternatives you've considered
A clear and concise description of any alternative solutions or features you've considered.

In this case the solution would be to not use Fagus, but just create a set and convert it back to a list, like this:
```python
print(list(set(a()))
```

#### Additional context
Add any other context or screenshots about the feature request here.
