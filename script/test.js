// AI-generated: shared test-doc generator, scans JSDoc comments from test files and outputs Markdown

import fs   from 'fs';
import path from 'path';

// ========== Argument Parser ==========

class ArgParser {

    /**
     * Parse process.argv into a key-value map.
     * Supports --key value and --key=value forms.
     * @private
     */
    static parse(argv) {
        const args = {};
        for (let i = 0; i < argv.length; i++) {
            const arg = argv[i];
            if (arg.startsWith('--')) {
                const eqIndex = arg.indexOf('=');
                if (eqIndex !== -1) {
                    args[arg.slice(2, eqIndex)] = arg.slice(eqIndex + 1);
                } else if (argv[i + 1] && !argv[i + 1].startsWith('--')) {
                    args[arg.slice(2)] = argv[++i];
                }
            }
        }
        return args;
    }
}

// ========== Comment Parser ==========

class TestCommentParser {

    /**
     * Parse all JSDoc blocks that start with "Verify that" from a file's source.
     * Does not require any specific function naming convention — only the comment matters.
     * Groups results by the function name extracted from "Verify that <name>".
     * @param {string} content - Raw source of the test file
     * @returns {Map<string, Array>} Map of group name -> array of test case objects
     */
    parse(content) {
        const groups = new Map();

        const regex = /\/\*\*([\s\S]*?)\*\//g;
        let match;

        while ((match = regex.exec(content)) !== null) {
            const block = match[1];

            const description = this._extractDescription(block);
            if (!description || !/^Verify that /i.test(description)) continue;

            const param    = this._extractParam(block);
            const returns  = this._extractReturns(block);
            const group    = this._extractGroup(description);
            const scenario = this._extractScenario(returns);
            const expected = returns ? returns.replace(/\s*—.*$/, '').trim() : '';
            const reason   = this._extractReason(block);

            if (!groups.has(group)) groups.set(group, []);
            groups.get(group).push({ description, input: param, expected, scenario, reason });
        }

        return groups;
    }

    /** @private */
    _extractDescription(block) {
        const lines = block.split('\n');
        const desc  = [];
        for (const line of lines) {
            const trimmed = line.replace(/^\s*\*\s?/, '').trim();
            if (trimmed.startsWith('@')) break;
            if (trimmed) desc.push(trimmed);
        }
        return desc.join(' ');
    }

    /** @private */
    _extractParam(block) {
        const match = block.match(/@param\s+\{[^}]+\}\s+\w+\s*-\s*(.+)/);
        return match ? match[1].trim() : '';
    }

    /** @private */
    _extractReturns(block) {
        const match = block.match(/@returns?\s+\{[^}]+\}\s+(.+)/);
        return match ? match[1].trim() : '';
    }

    /** @private */
    _extractGroup(description) {
        const match = description.match(/Verify that (\w+)/i);
        return match ? match[1] : 'Other';
    }

    /** @private */
    _extractScenario(returns) {
        if (!returns) return '';
        const match = returns.match(/—\s*(.+)$/);
        return match ? match[1].trim() : '';
    }

    /** @private */
    _extractReason(block) {
        const match = block.match(/@reason\s+(.+)/);
        return match ? match[1].trim() : '';
    }
}

// ========== Renderer ==========

class TestDocRenderer {

    /**
     * Render all groups into a Markdown section.
     * @param {Map<string, Array>} groups - Parsed test groups
     * @param {string} label - Section heading
     * @param {number} startIndex - TC number offset
     * @returns {{ md: string, count: number }}
     */
    renderSection(groups, label, startIndex) {
        let md       = `## ${label}\n\n`;
        let tcNumber = startIndex;
        let count    = 0;

        // AI-generated: HTML table with colgroup so column widths are explicit and readable
        // in VS Code preview and GitHub — Markdown tables have no width control.
        for (const [fnName, cases] of groups) {
            md += `### \`${fnName}\`\n\n`;
            // AI-generated: width on <th> is the most reliable way to lock column proportions
            // in VS Code preview — colgroup percentages are often ignored when <code> content is wide.
            const S = 'style="overflow-wrap:anywhere;word-break:break-word"';
            md += '<table style="width:100%;table-layout:fixed"><thead><tr>';
            md += '<th style="width:5%">#</th>';
            md += '<th style="width:20%">Description</th>';
            md += '<th style="width:22%">Input</th>';
            md += '<th style="width:18%">Output</th>';
            md += '<th style="width:8%">Scenario</th>';
            md += '<th style="width:27%">Reason</th>';
            md += '</tr></thead>\n<tbody>\n';

            for (const tc of cases) {
                const tcId = `TC-${String(tcNumber).padStart(3, '0')}`;
                md += `<tr><td ${S}>${tcId}</td>`;
                md += `<td ${S}>${tc.description}</td>`;
                md += `<td ${S}><code>${tc.input}</code></td>`;
                md += `<td ${S}><code>${tc.expected}</code></td>`;
                md += `<td ${S}>${tc.scenario}</td>`;
                md += `<td ${S}>${tc.reason}</td></tr>\n`;
                tcNumber++;
                count++;
            }

            md += '</tbody></table>\n\n---\n\n';

        }

        return { md, count };
    }
}

// ========== Main ==========

const args  = ArgParser.parse(process.argv.slice(2));
const files = args.files ? args.files.split(',') : [];
const out   = args.out;
const title = args.title || 'Test Specification';

if (!files.length || !out) {
    console.error('Usage: gen-test-doc.js --files <file1,file2> --out <output.md> [--title <title>]');
    process.exit(1);
}

const parser   = new TestCommentParser();
const renderer = new TestDocRenderer();

let md = `# ${title}\n\n`;
md += `> **Generated at**: ${new Date().toISOString()}  \n`;
md += '> **Note**: This document is auto-generated. Do not edit manually.  \n\n';
md += '---\n\n';

let totalCount = 0;
let tcStart    = 1;

for (const filePath of files) {
    const absPath = path.resolve(filePath);

    if (!fs.existsSync(absPath)) {
        console.warn(`Warning: file not found, skipping: ${absPath}`);
        continue;
    }

    const content                = fs.readFileSync(absPath, 'utf8');
    const groups                 = parser.parse(content);
    const basename               = path.basename(absPath);
    // main.test.js is always the public API test file; all others are internal unit tests
    const label                  = basename === 'main.test.js'
                                     ? `Public API Tests (${basename})`
                                     : `Internal Unit Tests (${basename})`;
    const { md: section, count } = renderer.renderSection(groups, label, tcStart);

    md         += section;
    totalCount += count;
    tcStart    += count;
}

fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
fs.writeFileSync(path.resolve(out), md);
console.log(`Generated: ${out}`);
console.log(`Total test cases: ${totalCount}`);
