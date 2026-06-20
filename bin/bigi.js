#!/usr/bin/env node
const { spawn } = require('child_process');
const path = require('path');

// Locate the python entry point in the package root
const pythonScript = path.join(__dirname, '../bigi-cli');

// Spawn the Python child process and pipe terminal arguments
const child = spawn('python3', [pythonScript, ...process.argv.slice(2)], {
    stdio: 'inherit'
});

child.on('exit', (code) => {
    process.exit(code || 0);
});

child.on('error', (err) => {
    console.error('Error: Failed to launch the Python backend.');
    console.error('Please ensure Python 3 is installed and available in your PATH as "python3".');
    console.error(err.message);
    process.exit(1);
});
