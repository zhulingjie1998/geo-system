const fs = require('fs');
const path = require('path');

let compile;
try {
    compile = require('@vue/compiler-sfc');
} catch(e) {
    const modPath = path.join(__dirname, 'node_modules', '.pnpm');
    const dirs = fs.readdirSync(modPath).filter(d => d.includes('compiler-sfc'));
    if (dirs.length) {
        compile = require(path.join(modPath, dirs[0], 'node_modules', '@vue/compiler-sfc'));
    }
}

if (!compile) {
    console.log('Cannot find @vue/compiler-sfc');
    process.exit(1);
}

const source = fs.readFileSync('C:/Users/Administrator/Desktop/geo-ops-system/geo-ops-system/frontend/src/views/PublishAiWritePage.vue', 'utf-8');

try {
    const { descriptor, errors } = compile.parse(source);
    if (errors && errors.length) {
        console.log('PARSE ERRORS:', JSON.stringify(errors, null, 2));
    } else {
        console.log('PARSE SUCCESS');
        console.log('Has template:', !!descriptor.template);
        if (descriptor.template) {
            try {
                const result = compile.compileTemplate({
                    source: descriptor.template.content,
                    filename: 'PublishAiWritePage.vue',
                    id: 'test'
                });
                console.log('TEMPLATE COMPILE SUCCESS');
            } catch(te) {
                console.log('TEMPLATE COMPILE ERROR:', te.message);
                if (te.loc) console.log('Location:', JSON.stringify(te.loc));
            }
        }
    }
} catch(e) {
    console.log('PARSE EXCEPTION:', e.message);
    if (e.loc) console.log('Location:', JSON.stringify(e.loc));
}
