import ast
import math
import random
import re
from pathlib import Path


WEIGHTS_PATH = Path(r"C:\Users\james\Downloads\new_model_weights.txt")

NEW_WORDS = ["nebula", "quasar", "pulsar", "galaxy", "planet", "comet ", "meteor", "astron"]
NEW_UNIQUE = sorted(set(NEW_WORDS))
NEW_CHARS = sorted(set("".join(NEW_WORDS)))
NEW_VOCAB_SIZE = len(NEW_CHARS)
NEW_CHAR_TO_INT = {ch: i for i, ch in enumerate(NEW_CHARS)}
NEW_INT_TO_CHAR = {i: ch for i, ch in enumerate(NEW_CHARS)}

TARGET_REAL_WORDS = [
    "rescue",
    "please",
    "resume",
    "screen",
    "plague",
    "sample",
    "season",
    "census",
]

SEQ_LEN = 6
EMBED_DIM = 16
LATENT_DIM = SEQ_LEN * EMBED_DIM
FLOW_DIM = LATENT_DIM // 2
NUM_LAYERS = 24


def parse_weight_dump(path: Path):
    layer_re = re.compile(r"^LAYER: (.+)$")
    shape_re = re.compile(r"^SHAPE: \[(.*)\]$")
    lines = path.read_text(encoding="utf-8").splitlines()
    items = {}
    i = 0
    while i < len(lines):
        m = layer_re.match(lines[i].strip())
        if not m:
            i += 1
            continue
        name = m.group(1)
        sm = shape_re.match(lines[i + 1].strip())
        shape = tuple(int(x.strip()) for x in sm.group(1).split(",")) if sm else None
        j = i + 2
        while j < len(lines) and not lines[j].startswith("WEIGHTS:"):
            j += 1
        payload = lines[j][len("WEIGHTS:"):].strip()
        k = j + 1
        while k < len(lines) and not lines[k].startswith("------------------------------") and not layer_re.match(lines[k].strip()):
            payload += "\n" + lines[k]
            k += 1
        items[name] = {"shape": shape, "weights": ast.literal_eval(payload)}
        i = k
    return items


def flatten(x):
    if isinstance(x, list):
        for item in x:
            yield from flatten(item)
    else:
        yield float(x)


def matvec(weight, bias, vec):
    out = []
    for row, b in zip(weight, bias):
        s = b
        for w, v in zip(row, vec):
            s += w * v
        out.append(s)
    return out


def relu(vec):
    return [v if v > 0.0 else 0.0 for v in vec]


class CouplingLayer:
    def __init__(self, w1, b1, w2, b2, mask_left):
        self.w1 = w1
        self.b1 = b1
        self.w2 = w2
        self.b2 = b2
        self.mask_left = mask_left

    def net(self, x):
        return matvec(self.w2, self.b2, relu(matvec(self.w1, self.b1, x)))

    def forward(self, x, reverse=False):
        left = x[:FLOW_DIM]
        right = x[FLOW_DIM:]
        if self.mask_left:
            shift = self.net(right)
            if reverse:
                left = [a - d for a, d in zip(left, shift)]
            else:
                left = [a + d for a, d in zip(left, shift)]
        else:
            shift = self.net(left)
            if reverse:
                right = [a - d for a, d in zip(right, shift)]
            else:
                right = [a + d for a, d in zip(right, shift)]
        return left + right


class EnhancedTextFlow:
    def __init__(self, state):
        self.embed = state["embed.weight"]["weights"]
        self.output_w = state["output.weight"]["weights"]
        self.output_b = state["output.bias"]["weights"]
        self.layers = []
        for i in range(NUM_LAYERS):
            prefix = f"flow.layers.{i}.net"
            w1 = state[f"{prefix}.0.weight"]["weights"]
            b1 = state[f"{prefix}.0.bias"]["weights"]
            w2 = state[f"{prefix}.2.weight"]["weights"]
            b2 = state[f"{prefix}.2.bias"]["weights"]
            self.layers.append(CouplingLayer(w1, b1, w2, b2, mask_left=bool(i % 2)))

    def embed_words(self, x_tokens):
        batch = []
        for row in x_tokens:
            seq = [self.embed[idx] for idx in row]
            batch.append(seq)
        return batch

    def flow_forward(self, x):
        for layer in self.layers:
            x = layer.forward(x, reverse=False)
        return x

    def flow_reverse(self, x):
        for layer in reversed(self.layers):
            x = layer.forward(x, reverse=True)
        return x

    def output_logits(self, embeds):
        batch = []
        for seq in embeds:
            seq_logits = []
            for vec in seq:
                row_logits = [b + sum(w * v for w, v in zip(row, vec)) for row, b in zip(self.output_w, self.output_b)]
                seq_logits.append(row_logits)
            batch.append(seq_logits)
        return batch


def hidden_vectors_for_targets(model, targets):
    return [model.flow_reverse(v) for v in targets]


def rebind_output_to_words(model, hidden_vectors, words):
    letters = NEW_CHARS
    dim = EMBED_DIM
    class_vectors = {ch: [] for ch in letters}
    for word, seq in zip(words, hidden_vectors):
        chunks = [seq[i:i + dim] for i in range(0, len(seq), dim)]
        for ch, vec in zip(word, chunks):
            class_vectors[ch].append(vec)
    weights = []
    bias = []
    for ch in letters:
        vectors = class_vectors[ch]
        if vectors:
            centroid = [sum(vals) / len(vals) for vals in zip(*vectors)]
        else:
            centroid = [0.0] * dim
        weights.append(centroid)
        bias.append(-0.5 * sum(v * v for v in centroid))
    model.output_w = weights
    model.output_b = bias


def train_output_head(model, hidden_vectors, words, steps=2500, lr=0.05):
    samples = []
    for word, seq in zip(words, hidden_vectors):
        chunks = [seq[i:i + EMBED_DIM] for i in range(0, len(seq), EMBED_DIM)]
        for ch, vec in zip(word, chunks):
            samples.append((vec, NEW_CHAR_TO_INT[ch]))

    w = ast.literal_eval(repr(model.output_w))
    b = ast.literal_eval(repr(model.output_b))

    for _ in range(steps):
        errors = 0
        for x, y in samples:
            scores = [b[c] + sum(w[c][d] * x[d] for d in range(EMBED_DIM)) for c in range(NEW_VOCAB_SIZE)]
            pred = max(range(NEW_VOCAB_SIZE), key=lambda c: scores[c])
            if pred != y:
                errors += 1
                for d in range(EMBED_DIM):
                    w[y][d] += lr * x[d]
                    w[pred][d] -= lr * x[d]
                b[y] += lr
                b[pred] -= lr
        if errors == 0:
            break
    model.output_w = w
    model.output_b = b


def build_targets():
    targets = []
    for i in range(len(NEW_UNIQUE)):
        v = [0.0] * LATENT_DIM
        v[i % LATENT_DIM] = 20.0
        targets.append(v)
    return targets


def decode_words(model, targets):
    recovered = []
    latent = [model.flow_reverse(v) for v in targets]
    embeds = [vecs if isinstance(vecs[0], list) else [vecs[i:i + EMBED_DIM] for i in range(0, len(vecs), EMBED_DIM)] for vecs in latent]
    logits = model.output_logits(embeds)
    for seq in logits:
        word = "".join(NEW_INT_TO_CHAR[max(range(len(row)), key=lambda j: row[j])] for row in seq)
        recovered.append(word)
    return recovered


def clone_state(state):
    return {k: {"shape": v["shape"], "weights": ast.literal_eval(repr(v["weights"]))} for k, v in state.items()}


def perturb_one(state, name, magnitude):
    mutated = clone_state(state)
    weights = mutated[name]["weights"]
    if "bias" in name:
        weights[0] += magnitude
    else:
        weights[0][0] += magnitude
    return mutated


def perturb_row(state, name, magnitude):
    mutated = clone_state(state)
    weights = mutated[name]["weights"]
    if "bias" in name:
        for i in range(len(weights)):
            weights[i] += magnitude
    else:
        for j in range(len(weights[0])):
            weights[0][j] += magnitude
    return mutated


def main():
    state = parse_weight_dump(WEIGHTS_PATH)
    model = EnhancedTextFlow(state)
    print("Vocab:", "".join(NEW_CHARS))
    print("Words:", ", ".join(NEW_UNIQUE))
    print("Target anchors: 20.0")

    targets = build_targets()
    baseline = decode_words(model, targets)
    print("\nBaseline recovery:")
    for i, word in enumerate(baseline):
        print(f"  anchor {i}: {word!r}")

    print("\nRebinding decoder to other real words:")
    print("  targets:", ", ".join(TARGET_REAL_WORDS))
    hidden = hidden_vectors_for_targets(model, targets)
    train_output_head(model, hidden, TARGET_REAL_WORDS)
    rebased = decode_words(model, targets)
    for i, word in enumerate(rebased):
        print(f"  anchor {i}: {word!r}")

    candidates = [
        "flow.layers.0.net.0.weight",
        "flow.layers.12.net.0.weight",
        "flow.layers.23.net.0.weight",
        "flow.layers.23.net.2.bias",
        "output.weight",
        "output.bias",
    ]
    magnitudes = [0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0]

    chosen = None
    changed = baseline
    for name in candidates:
        for magnitude in magnitudes:
            perturbed_state = perturb_one(state, name, magnitude)
            perturbed_model = EnhancedTextFlow(perturbed_state)
            trial = decode_words(perturbed_model, targets)
            if trial != baseline:
                chosen = (name, magnitude)
                changed = trial
                break
        if chosen:
            break

    if chosen:
        name, magnitude = chosen
        print(f"\nAfter perturbing {name} by {magnitude}:")
        for i, word in enumerate(changed):
            flag = "changed" if word != baseline[i] else "same"
            print(f"  anchor {i}: {word!r} [{flag}]")

        print("\nOriginal vs perturbed:")
        for i, (a, b) in enumerate(zip(baseline, changed)):
            print(f"  {i}: {a!r} -> {b!r}")
    else:
        print("\nNo scalar perturbation changed the decoded words.")
        row_candidates = [
            "output.weight",
            "output.bias",
            "flow.layers.0.net.0.weight",
            "flow.layers.23.net.2.weight",
        ]
        for name in row_candidates:
            for magnitude in [2.0, 5.0, 10.0]:
                perturbed_state = perturb_row(state, name, magnitude)
                perturbed_model = EnhancedTextFlow(perturbed_state)
                trial = decode_words(perturbed_model, targets)
                if trial != baseline:
                    print(f"\nAfter row perturbing {name} by {magnitude}:")
                    for i, word in enumerate(trial):
                        flag = "changed" if word != baseline[i] else "same"
                        print(f"  anchor {i}: {word!r} [{flag}]")
                    print("\nOriginal vs perturbed:")
                    for i, (a, b) in enumerate(zip(baseline, trial)):
                        print(f"  {i}: {a!r} -> {b!r}")
                    return
        print("\nNo tested row-level perturbation changed the decoded words either.")


if __name__ == "__main__":
    main()
