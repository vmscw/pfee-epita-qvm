# Requirements Tree

## Description

`requirements-tree.mmd` propose a representation of our technical needs behind
the multiprogramming solution. Its goal is to help determine our solution
criterias using an alternative way to see the needs lying behind the criterias
we want to define.

A tree in the forest always has a depth of 3. In each tree, each layer always
has the same role :
- The root node represents a business need: at the end of the day, what is it
  we wish to gain from quantum multiprogramming ?
- The middle node represents general solutions to satisfy said need.
- The leaf node represents ways to pratically implement the solution.

Using this logic, the graph helps us connect business needs to technical needs.
Once the process of creating the graph is finished, the leaf nodes specify a
list of requirements we can use to define the criterias we shall consider when
researching existing multiprogramming solutions in the current state of the art.

## Directives

- The graph is statically defined using the Mermaid.js graph js format. It can
  be compiled to a visual graph using either Mermaid's
  [Live Editor](https://mermaid.ai/live/edit) or
  [mermaid-cli](https://github.com/mermaid-js/mermaid-cli).
- Visually, trees are represented from top to bottom (following mermaid.js's
  output format).
- Descriptions inside the nodes are made to be straightforward and use concrete,
  practical verbs. This helps making the graph more concise and easier to read.
- The graph is not meant to provide an exhaustive list of potential solutions.
  It should only remain in the technical context of "multiprogramming
  compilers and schedulers". For instance, if one solution to a business need is
  to "improve QPU throughput", then we could definitely optimize said throughput 
  over a given duration of time by optimizing the execution speed of gates and
  measurements. However, such solutions belong in the realm of QPU physical
  improvements, which is not part of the scope defined by our analysis.
