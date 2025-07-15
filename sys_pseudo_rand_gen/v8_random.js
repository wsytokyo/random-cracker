/**
 * @file A simple script to generate and print a sequence of pseudo-random floats.
 *
 * This script is used by the test suite to generate live data from Node.js's
 * `Math.random()` function, which is typically implemented using V8's engine.
 *
 * @usage node pseudo_random.js [count]
 *
 * @argument {number} [count=10] - The number of random floats to generate.
 */

function main() {
  const [, , count = 10] = process.argv;
  for (let i = 0; i < Number(count); i++) {
    console.log(Math.random());
  }
}

main();
