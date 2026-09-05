/**
 * Vapi -> Google Calendar + Google Sheet bridge.
 *
 * Handles two kinds of POST from Vapi at the same URL:
 *   1. tool-calls        : the assistant called book_meeting. Creates the calendar event.
 *   2. end-of-call-report: the call ended. Appends one row to the "Calls" sheet
 *                          with the outcome, note, transcript and recording link.
 *
 * Deployed as a web app (Execute as: Me, Who has access: Anyone). Because
 * Apps Script cannot read request headers, the URL carries a secret:
 *   https://script.google.com/macros/s/.../exec?key=YOUR_SECRET
 * Set the same value in SECRET below.
 */

var SECRET = 'CHANGE_ME_TO_A_LONG_RANDOM_STRING';
var SHEET_NAME = 'Calls';
var TIMEZONE = 'Asia/Dubai';

function doPost(e) {
  if (!e || !e.parameter || e.parameter.key !== SECRET) {
    return jsonResponse({ error: 'unauthorised' });
  }
  var body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (err) {
    return jsonResponse({ error: 'bad json' });
  }
  var message = body.message || {};
  try {
    if (message.type === 'tool-calls') {
      return jsonResponse({ results: handleToolCalls(message) });
    }
    if (message.type === 'end-of-call-report') {
      logCall(message);
      return jsonResponse({ ok: true });
    }
    return jsonResponse({ ok: true, ignored: message.type });
  } catch (err) {
    logError(err, message);
    if (message.type === 'tool-calls') {
      return jsonResponse({
        results: (message.toolCallList || []).map(function (tc) {
          return { toolCallId: tc.id, result: 'Calendar error: ' + err.message };
        })
      });
    }
    return jsonResponse({ error: String(err) });
  }
}

// Lets you open the URL in a browser to check the deployment is alive.
function doGet(e) {
  return ContentService.createTextOutput('Vapi bridge is up. POST only.');
}

function handleToolCalls(message) {
  var vars = variableValues(message);
  return (message.toolCallList || []).map(function (tc) {
    if (tc.name !== 'book_meeting') {
      return { toolCallId: tc.id, result: 'Unknown tool ' + tc.name };
    }
    var args = tc.arguments || {};
    if (typeof args === 'string') { try { args = JSON.parse(args); } catch (err) { args = {}; } }
    var event = createEvent(vars, args.confirmed_by || vars.contact_name || '');
    return {
      toolCallId: tc.id,
      result: 'Booked. Event "' + event.getTitle() + '" created for ' +
        Utilities.formatDate(event.getStartTime(), TIMEZONE, "EEEE d MMMM 'at' h:mm a") + ' Dubai time.'
    };
  });
}

function variableValues(message) {
  var call = message.call || {};
  var overrides = call.assistantOverrides || {};
  return overrides.variableValues || {};
}

function createEvent(vars, confirmedBy) {
  if (!vars.start_iso || !vars.end_iso) {
    throw new Error('start_iso or end_iso missing from call variables');
  }
  var start = new Date(vars.start_iso);
  var end = new Date(vars.end_iso);
  var title = vars.title || ('Meeting with ' + (vars.contact_name || confirmedBy));
  var description = [
    'Confirmed by phone with ' + (confirmedBy || vars.contact_name || 'the contact') + ' via AI assistant.',
    '',
    'About: ' + (vars.brief || ''),
  ].join('\n');
  var options = { location: vars.location || '', description: description };
  if (vars.attendee_email) {
    options.guests = vars.attendee_email;
    options.sendInvites = true;
  }
  return CalendarApp.getDefaultCalendar().createEvent(title, start, end, options);
}

function logCall(message) {
  var sheet = getSheet();
  var vars = variableValues(message);
  var call = message.call || {};
  var customer = message.customer || call.customer || {};
  var artifact = message.artifact || {};
  var outcome = findOutcome(artifact.structuredOutputs);
  var analysis = message.analysis || {};
  var startedAt = message.startedAt ? new Date(message.startedAt) : new Date();
  var endedAt = message.endedAt ? new Date(message.endedAt) : null;
  var durationSec = endedAt ? Math.round((endedAt - startedAt) / 1000) : '';
  sheet.appendRow([
    Utilities.formatDate(startedAt, TIMEZONE, 'yyyy-MM-dd HH:mm'),
    vars.contact_name || customer.name || '',
    customer.number || '',
    outcome.outcome || '',
    outcome.note || '',
    outcome.proposed_time_text || '',
    vars.when_spoken || '',
    outcome.identity_confirmed === undefined ? '' : String(outcome.identity_confirmed),
    outcome.disclosed_ai === undefined ? '' : String(outcome.disclosed_ai),
    message.endedReason || '',
    durationSec,
    analysis.summary || '',
    artifact.recordingUrl || (artifact.recording && artifact.recording.mono && artifact.recording.mono.combinedUrl) || '',
    call.id ? 'https://dashboard.vapi.ai/calls/' + call.id : '',
    artifact.transcript || ''
  ]);
}

function findOutcome(structuredOutputs) {
  if (!structuredOutputs) return {};
  var keys = Object.keys(structuredOutputs);
  for (var i = 0; i < keys.length; i++) {
    var entry = structuredOutputs[keys[i]];
    var result = entry && entry.result !== undefined ? entry.result : entry;
    if (result && typeof result === 'object' && result.outcome) return result;
  }
  return {};
}

function getSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
  }
  if (sheet.getLastRow() === 0) {
    sheet.appendRow([
      'Called at (Dubai)', 'Contact', 'Number', 'Outcome', 'Note', 'They proposed', 'Time offered',
      'Identity confirmed', 'AI disclosed', 'Ended reason', 'Seconds', 'Summary', 'Recording', 'Dashboard', 'Transcript'
    ]);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function logError(err, message) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName('Errors') || ss.insertSheet('Errors');
    sheet.appendRow([new Date(), String(err), JSON.stringify(message).slice(0, 5000)]);
  } catch (ignore) {}
}

function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

/** Run this once from the editor to grant Calendar and Sheets permissions and to test. */
function testBooking() {
  var start = new Date(); start.setDate(start.getDate() + 1); start.setHours(15, 0, 0, 0);
  var end = new Date(start.getTime() + 30 * 60000);
  var event = createEvent({
    start_iso: start.toISOString(), end_iso: end.toISOString(),
    title: 'TEST meeting from Vapi bridge', contact_name: 'Test Contact',
    location: 'Test location', brief: 'Delete me.'
  }, 'Test Contact');
  getSheet();
  Logger.log('Created test event: ' + event.getId());
}
