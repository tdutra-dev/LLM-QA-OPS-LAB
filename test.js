const data = [
  { name: "A", score: "10" },
  { name: "B", score: "5" },
  { name: "C", score: null }
];

// Task:

// convert score → number
// rimuovi invalid
// ordina DESC

const valid = [];
const invalid = [];

data.forEach(item => {
    const score = Number(item.score);
    if (isNaN(score)) {
        invalid.push(item);
    } else {
        valid.push({ ...item, score });
    }
});

valid.sort((a, b) => b.score - a.score);