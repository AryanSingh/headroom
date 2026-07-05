const fs = require('fs');
const file = 'dashboard/src/pages/Overview.jsx';
let content = fs.readFileSync(file, 'utf8');
content = content.replace(
  'stats.recent_requests.slice(0, 8)',
  '[...stats.recent_requests].reverse().slice(0, 8)'
);
fs.writeFileSync(file, content);
