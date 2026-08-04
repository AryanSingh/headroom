const assert = require('node:assert/strict');
const test = require('node:test');

const { parseStatsPayload } = require('../out/stats.js');

test('parses the current since-restart stats contract', () => {
    assert.deepEqual(
        parseStatsPayload({
            summary: { scope: 'since_restart', saved: 1250 },
            cost: { scope: 'since_restart', savings_usd: 0.03125 },
            requests: { scope: 'since_restart', total: 7 },
        }),
        { tokensSaved: 1250, dollarsSaved: 0.03125, requestsCompressed: 7 },
    );
});

test('missing or malformed counters fail closed to zero', () => {
    assert.deepEqual(parseStatsPayload({ summary: { saved: 'not-a-number' } }), {
        tokensSaved: 0,
        dollarsSaved: 0,
        requestsCompressed: 0,
    });
});
