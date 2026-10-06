# Fantacalcio Mantra Auction Companion — UI Requirements

Version 0.1 · Draft for review

## 1. Purpose

A simple web app used live during a Fantacalcio Mantra auction. It records every sale (player, buying team, price), tracks my own squad and budget, and shows which players are still available for a chosen role. A database of past statistics and the current player pool already exists.

**Primary user:** me, during a live auction, on a laptop (secondary: tablet). Speed of data entry matters more than visual polish.

## 2. Assumptions (please confirm)

- Single user, no login or multi-user sync needed in v1.
- Desktop-first. The layout must still work on a tablet.
- My budget is 500 credits. My roster is 5 goalkeepers + 20 outfield players (25 total).
- Other teams have the same rules (budget 500, 5 + 20). The number of teams and their names are configurable.
- Prices are whole numbers (credits), minimum 1.
- Mantra roles are used: Por, Dd, Ds, Dc, B, E, M, C, W, T, A, Pc. A player can have more than one role.
- "Outfield" means any non-Por player.

## 3. Layout

Two-column layout with a top bar.

```
+--------------------------------------------------------------+
| Top bar: App name | Budget left | Slots left | Undo | Settings|
+------------------------------------------+-------------------+
| MAIN AREA                                | RIGHT SIDEBAR     |
|                                          |                   |
| [ Sale entry bar ]                       | My team           |
|  Player ___ Team ___ Price ___ [Record]  |  Budget + slots   |
|                                          |  Por (x/5)        |
| [ Role filter chips ]                    |  Outfield (x/20)  |
|                                          |                   |
| [ Available players table ]              | Other teams       |
|                                          |  (collapsed list) |
| [ Recent sales log ]                     |                   |
+------------------------------------------+-------------------+
```

## 4. Components and requirements

### 4.1 Top bar

- Shows my remaining budget, e.g. "Budget: 312 / 500".
- Shows slots filled, e.g. "Por 2/5 · Outfield 9/20".
- Undo button reverts the last recorded sale.
- Settings link (team names, reset auction, export).

### 4.2 Sale entry bar (main page, top)

Purpose: record a sale in a few keystrokes.

| Field | Behavior |
|---|---|
| Player | Text input with autocomplete over **available** players only. Matches on partial name, accent- and case-insensitive. Arrow keys + Enter to select. Shows role and club in each suggestion. |
| Team | Dropdown or autocomplete. "My team" is pre-listed first. Remembers the last used team. |
| Price | Numeric input, whole numbers, minimum 1. |
| Record | Button. Enter key submits from any field. |

Requirements:

- Keyboard-only flow: Player, Tab, Team, Tab, Price, Enter. After submit, focus returns to Player and the form clears.
- Show a confirmation toast ("Lautaro Martinez sold to Team X for 45") with an Undo link.
- Validation (inline, blocks submit):
  - Player must exist and be unsold.
  - Price must be at least 1.
  - The buying team must have a free slot for that player's role group (Por or outfield).
  - The price must leave enough budget for the buying team to fill its remaining slots at 1 credit each. Maximum bid = remaining budget − (remaining empty slots − 1).
- If the name I type matches a player who is already sold, show "Already sold to Team X for N" instead of "no match", with an Edit option.
- If I attempt an invalid sale, show the specific reason (e.g. "Team X has no goalkeeper slots left").

### 4.3 Role filter

- Chips for: All, Por, Dd, Ds, Dc, B, E, M, C, W, T, A, Pc. Single-select in v1.
- Optional quick groups: Goalkeepers, Defenders, Midfielders, Forwards.
- Selected role persists while I work.

### 4.4 Available players table (main area)

- Lists unsold players matching the selected role.
- Default columns: Name, Club, Role(s), plus key stats from the existing database (e.g. last season fantavoto average, appearances, goals/assists, suggested price if available in the DB).
- Sortable by any column. Default sort: suggested price or average rating, descending.
- Text search box to narrow the list further.
- Clicking a row pre-fills the Player field in the sale entry bar.
- Row action "Sold…" opens the same entry flow with the player pre-selected.
- A sold player disappears from the list immediately and appears in the sales log (4.5).
- A "Show sold" toggle (off by default) brings sold players back into the table, greyed out, with a badge showing the buyer and price (e.g. "Team X · 45"). Turning it off hides them again.
- Shows a count: "42 available".
- Optional (v1.1): expand a row to see past-season stats.

### 4.5 Recent sales log (main area, bottom)

- Reverse-chronological list: Player, Role, Team, Price, time.
- Each row has an Edit and Delete action (corrects mistakes beyond the last sale).
- Filter by team.
- Search by player name, so I can quickly check who bought a player and for how much.
- Newly recorded sales are briefly highlighted at the top of the log.

### 4.6 Right sidebar: my team

- Header: team name, budget left, spent total.
- Two sections:
  - **Goalkeepers** (x/5): list of players with price; empty slots shown as placeholders.
  - **Outfield** (x/20): list of players with role(s) and price; empty slots shown as placeholders.
- Optionally group outfield players by role (Dif, Cen, Att) or sort by role.
- Clicking a player shows details or offers "Remove" (returns the player to the available pool and refunds budget).
- Visual warning when budget is tight (e.g. max bid falls below a threshold) or when a role group is full.
- Shows "Max bid you can place" as a highlighted number.

### 4.7 Right sidebar: other teams

- Collapsed list of teams, each showing budget left and slots filled.
- Expanding a team shows its players and prices (same layout as my team).
- Helps me see who can still afford what.

## 5. States

| Area | State | Behavior |
|---|---|---|
| Available players | Loading | Skeleton rows |
| Available players | Empty (role exhausted) | "No available players for this role" |
| Available players | Error loading | Message with Retry |
| Sale entry | No match | "No available player found. It may already be sold." |
| My team | Empty | Placeholder slots, full budget shown |
| My team | Roster complete | Success banner; entry for my team disabled |
| Sales log | Empty | "No sales recorded yet" |
| Save failure | Network/DB error | Toast with Retry; the sale is not shown as recorded until saved |

## 6. Non-functional requirements

- **Speed:** autocomplete and table updates feel instant (under 100 ms for typical pool size, a few hundred to ~1,000 players).
- **Reliability:** every sale is saved immediately; refreshing the page never loses data.
- **Accessibility:** full keyboard operation, visible focus states, labels on all inputs, sufficient color contrast, status changes announced to screen readers. Do not rely on color alone for warnings.
- **Responsive:** on narrow screens the sidebar moves below the main area or into a toggleable drawer.
- **Data:** read existing player and stats tables; add tables for teams and sales (player, team, price, timestamp).
- **Export:** CSV export of all sales and each team's roster (nice to have).

## 7. Out of scope for v1

- Multi-user real-time sync
- Authentication
- Bid timers or live bidding
- Automated player recommendations
- Lineup/formation planning after the auction

## 8. Open questions

1. How many teams take part, and do you want to name them in advance?
2. Do all teams share the 500 budget and 5 + 20 roster limits, or only yours?
3. Is there a minimum price per player (1 credit) enforced by your league?
4. Which stats and columns from your database matter most when deciding to bid?
5. Do players have a single role or multiple Mantra roles in your data? Should the filter match any of a player's roles?
6. Should the app suggest a price for each player (from past stats), or only show stats?
7. Do you need the app to work on a phone during the auction?
8. What stack and database do you already use? This affects how sales are stored and how real-time the updates are.
9. Should I be able to mark players as "targets" or "avoid" before the auction starts?

## 9. Suggested next steps

1. Confirm the assumptions and answer the open questions.
2. Sketch a wireframe of the main page based on section 3.
3. Define the data model (teams, sales) against your existing database.
4. Build the sale entry flow and available-players table first, since they are the core of the experience.