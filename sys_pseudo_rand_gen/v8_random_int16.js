/**
 * @file A simple script to generate and print a sequence of pseudo-random integers.
 *
 * This script is used by the test suite to generate integer data by scaling the
 * output of `Math.random()`.
 *
 * @usage node pseudo_random_int.js [count]
 *
 * @argument {number} [count=10] - The number of random integers to generate.
 */

function main() {
  const MAX = 2 ** 16;
  const [, , count = 10] = process.argv;
  for (let i = 0; i < Number(count); i++) {
    console.log(Math.floor(Math.random() * MAX));
  }
}

main();
