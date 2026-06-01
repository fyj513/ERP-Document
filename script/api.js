// AI-generated: API-doc generator, parses structured JSDoc sections into Markdown tables

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

// ========== API Comment Parser ==========

class ApiCommentParser {

    /**
     * Parse public API entries from a source file.
     * A JSDoc block is public when it has @example and no @private.
     * Reads the structured format: Inputs:, Outputs:, Throws:, Rules: named sections.
     * @param {string} content - Raw source of the file
     * @param {string} sectionName - Display name for this section in the output doc
     * @returns {{ sectionName: string, functions: Array }}
     * @private
     */
    parse(content, sectionName) {
        const functions  = [];
        const lines      = content.split('\n');
        const blockRegex = /\/\*\*((?:[^*]|\*(?!\/))*)\*\//g;
        let match;

        while ((match = blockRegex.exec(content)) !== null) {
            const block = match[1];
            if (block.includes('@private')) continue;
            if (!block.includes('@example')) continue;

            // Line immediately after closing */ carries the function signature
            const beforeBlock = content.slice(0, match.index + match[0].length);
            const endLine     = beforeBlock.split('\n').length - 1;
            const signature   = this._extractSignature(lines, endLine + 1);
            if (!signature) continue;

            functions.push({
                signature,
                description: this._extractDescription(block),
                inputs:      this._extractInputs(block),
                outputs:     this._extractOutputs(block),
                throws:      this._extractThrows(block),
                rules:       this._extractRules(block),
                example:     this._extractExample(block),
            });
        }

        return { sectionName, functions };
    }

    /**
     * Read up to 3 lines starting at lineIndex to find a function/method signature.
     * Strips export / static / async / function keywords before matching.
     * @private
     */
    _extractSignature(lines, lineIndex) {
        for (let i = lineIndex; i < Math.min(lineIndex + 3, lines.length); i++) {
            const line = lines[i].trim();
            if (!line) continue;

            const cleaned = line
                .replace(/^export\s+/, '')
                .replace(/^static\s+/, '')
                .replace(/^async\s+/, '')
                .replace(/^function\s+/, '');

            const m = cleaned.match(/^(?:(get|set)\s+)?(\w+)\s*\(([^)]*)\)/);
            if (!m) continue;

            const [, accessor, name, rawParams] = m;
            if (accessor === 'get' || accessor === 'set') return `${accessor} ${name}`;
            return `${name}(${rawParams.trim()})`;
        }
        return null;
    }

    /**
     * Return the first non-empty, non-section-header line before any @ tag.
     * @private
     */
    _extractDescription(block) {
        const sectionHeader = /^(Inputs|Outputs|Throws|Rules):/;
        for (const line of block.split('\n')) {
            const trimmed = line.replace(/^\s*\*\s?/, '').trim();
            if (trimmed.startsWith('@')) break;
            if (trimmed && !sectionHeader.test(trimmed)) return trimmed;
        }
        return '';
    }

    /**
     * Collect all non-empty content lines under a named section header
     * (e.g. "Inputs:"), stopping at the next section header or @ tag.
     * @param {string} block
     * @param {string} sectionName - e.g. 'Inputs'
     * @returns {string[]}
     * @private
     */
    _extractSection(block, sectionName) {
        const lines     = block.split('\n');
        const stopAt    = /^(Inputs|Outputs|Throws|Rules):/;
        const result    = [];
        let   inSection = false;

        for (const line of lines) {
            const trimmed = line.replace(/^\s*\*\s?/, '').trim();

            if (trimmed === `${sectionName}:`) {
                inSection = true;
                continue;
            }
            if (!inSection) continue;

            // Stop at the next named section or any @ tag
            if (stopAt.test(trimmed) || trimmed.startsWith('@')) break;
            if (trimmed) result.push(trimmed);
        }

        return result;
    }

    /**
     * Parse Inputs: section lines.
     * Format per line: - name  {Type=default}  Description
     * @private
     */
    _extractInputs(block) {
        return this._extractSection(block, 'Inputs')
            .filter(l => l.startsWith('- '))
            .map(l => {
                // Match: - name  {TypeWithOptionalDefault}  Description
                const m = l.match(/^-\s+(\w+)\s+\{([^}]+)\}\s*(.*)/);
                if (!m) return null;

                const [, name, typeRaw, desc] = m;

                // Split "boolean=false" into type="boolean", defaultVal="false"
                const eqIdx      = typeRaw.lastIndexOf('=');
                const type       = eqIdx !== -1 ? typeRaw.slice(0, eqIdx)      : typeRaw;
                const defaultVal = eqIdx !== -1 ? typeRaw.slice(eqIdx + 1)     : null;

                return { name, type, defaultVal, desc: desc.trim() };
            })
            .filter(Boolean);
    }

    /**
     * Parse Outputs: section lines.
     * Format per line: - {Type}  Description
     * @private
     */
    _extractOutputs(block) {
        return this._extractSection(block, 'Outputs')
            .filter(l => l.startsWith('- '))
            .map(l => {
                const m = l.match(/^-\s+\{([^}]+)\}\s*(.*)/);
                if (!m) return null;
                return { type: m[1], desc: m[2].trim() };
            })
            .filter(Boolean);
    }

    /**
     * Parse Throws: section lines.
     * Format per line: - ErrorType  Condition description
     * @private
     */
    _extractThrows(block) {
        return this._extractSection(block, 'Throws')
            .filter(l => l.startsWith('- '))
            .map(l => {
                const m = l.match(/^-\s+(\S+)\s+(.*)/);
                if (!m) return null;
                return { errorType: m[1], condition: m[2].trim() };
            })
            .filter(Boolean);
    }

    /**
     * Parse Rules: section lines.
     * Format per line: N. condition text → behavior text
     * The → separator splits Condition and Behavior columns.
     * Inner → characters (without surrounding spaces) are preserved in the Behavior column.
     * @private
     */
    _extractRules(block) {
        return this._extractSection(block, 'Rules')
            .filter(l => /^\d+\./.test(l))
            .map(l => {
                // AI-generated: lazy .+? stops at the FIRST " → " (space-arrow-space),
                // so subsequent → inside the behavior column are left intact.
                const m = l.match(/^\d+\.\s+(.+?)\s+→\s+(.+)/);
                if (!m) {
                    const simple = l.match(/^\d+\.\s+(.+)/);
                    return simple ? { condition: simple[1].trim(), behavior: '' } : null;
                }
                return { condition: m[1].trim(), behavior: m[2].trim() };
            })
            .filter(Boolean);
    }

    /**
     * Extract the @example block (everything after the @example tag to end of comment).
     * @private
     */
    _extractExample(block) {
        const match = block.match(/@example([\s\S]*)/);
        if (!match) return '';
        return match[1]
            .split('\n')
            .map(l => l.replace(/^\s*\*\s?/, ''))
            .join('\n')
            .trim();
    }
}

// ========== Renderer ==========

class ApiDocRenderer {

    /**
     * Render all parsed sections into a full Markdown document.
     * @param {Array}    sections     - Array of parsed section objects
     * @param {string}   title        - Document title
     * @param {string[]} sourceLabels - Source file names shown in the header
     * @returns {string} Full Markdown string
     * @private
     */
    render(sections, title, sourceLabels) {
        let md = `# ${title}\n\n`;
        md += `> **Generated from**: ${sourceLabels.map(l => `\`${l}\``).join(', ')}  \n`;
        md += `> **Generated at**: ${new Date().toISOString()}  \n`;
        md += '> **Note**: This document is auto-generated. Do not edit manually.  \n\n';
        md += '---\n\n';

        for (const section of sections) {
            if (section.functions.length === 0) continue;
            md += `## ${section.sectionName}\n\n`;
            for (const fn of section.functions) {
                md += this._renderFunction(fn);
            }
        }
        return md;
    }

    /** @private */
    _renderFunction(fn) {
        let md = `### \`${fn.signature}\`\n\n`;
        if (fn.description) md += `${fn.description}\n\n`;

        // Parameters table
        if (fn.inputs.length > 0) {
            md += '**Parameters**\n\n';
            md += '| Name | Type | Default | Description |\n';
            md += '|---|---|---|---|\n';
            for (const p of fn.inputs) {
                const def = p.defaultVal !== null ? `\`${p.defaultVal}\`` : '*(required)*';
                md += `| \`${p.name}\` | \`${p.type}\` | ${def} | ${p.desc} |\n`;
            }
            md += '\n';
        }

        // Returns
        if (fn.outputs.length > 0) {
            const o = fn.outputs[0];
            md += `**Returns**: \`${o.type}\` — ${o.desc}\n\n`;
        }

        // Throws table — omitted when only (none) entries are present
        const realThrows = fn.throws.filter(t => t.errorType !== '(none)');
        if (realThrows.length > 0) {
            md += '**Throws**\n\n';
            md += '| Error | Condition |\n';
            md += '|---|---|\n';
            for (const t of realThrows) {
                md += `| \`${t.errorType}\` | ${t.condition} |\n`;
            }
            md += '\n';
        }

        // Rules table
        if (fn.rules.length > 0) {
            md += '**Rules**\n\n';
            const hasBehavior = fn.rules.some(r => r.behavior);
            if (hasBehavior) {
                md += '| # | Condition | Behavior |\n';
                md += '|---|---|---|\n';
                for (let i = 0; i < fn.rules.length; i++) {
                    const r = fn.rules[i];
                    md += `| ${i + 1} | ${r.condition} | ${r.behavior} |\n`;
                }
            } else {
                md += '| # | Rule |\n';
                md += '|---|---|\n';
                for (let i = 0; i < fn.rules.length; i++) {
                    md += `| ${i + 1} | ${fn.rules[i].condition} |\n`;
                }
            }
            md += '\n';
        }

        // Examples
        if (fn.example) {
            md += '**Examples**\n\n```javascript\n';
            md += fn.example + '\n';
            md += '```\n\n';
        }

        md += '---\n\n';
        return md;
    }
}

// ========== Main ==========

const args  = ArgParser.parse(process.argv.slice(2));
const out   = args.out;
const title = args.title || 'API Reference';

// --files format: path:SectionName,path:SectionName
const files = args.files
    ? args.files.split(',').map(entry => {
        const colonIdx = entry.lastIndexOf(':');
        return { path: entry.slice(0, colonIdx), sectionName: entry.slice(colonIdx + 1) };
    })
    : [];

if (!files.length || !out) {
    console.error('Usage: api.js --files <path:Section,...> --out <output.md> [--title <title>]');
    process.exit(1);
}

const parser   = new ApiCommentParser();
const renderer = new ApiDocRenderer();
const sections = [];

for (const file of files) {
    const absPath = path.resolve(file.path);
    if (!fs.existsSync(absPath)) {
        console.warn(`Warning: file not found, skipping: ${absPath}`);
        continue;
    }
    sections.push(parser.parse(fs.readFileSync(absPath, 'utf8'), file.sectionName));
}

const sourceLabels = files.map(f => path.basename(f.path));
const md           = renderer.render(sections, title, sourceLabels);

fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
fs.writeFileSync(path.resolve(out), md);

const total = sections.reduce((sum, s) => sum + s.functions.length, 0);
console.log(`Generated: ${out}`);
console.log(`Total functions documented: ${total}`);
