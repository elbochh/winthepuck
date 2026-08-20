const K = require("./build_docs.js");
const { P, Rich, H1, H2, Bullet, Code, Rule, makeTable, titleBlock,
        Document, Packer, Paragraph, TextRun, AlignmentType,
        ExternalHyperlink, PageBreak, numbering, sectionProps, fs } = K;

const URL = "https://winthepuck.azurewebsites.net";
const BLANK = " ";

const body = [
  ...titleBlock(
    "Project Phase 5 · Progress Report",
    "WinThePuck — Team & Progress Report",
    "Who we are, what we set out to do in Phase 5, and how far we got."
  ),

  // ---------------- team ----------------
  H1("1. Team information"),
  P("Project name: WinThePuck — an NHL game winner prediction website."),
  makeTable(
    ["Team member", "Student ID", "Main responsibility in Phase 5", "Email"],
    [
      ["Bechir Elloumi", BLANK, "Cloud deployment, model service, back end", "elloumi.bechir99@gmail.com"],
      [BLANK, BLANK, BLANK, BLANK],
      [BLANK, BLANK, BLANK, BLANK],
      [BLANK, BLANK, BLANK, BLANK],
    ],
    [2400, 1500, 3400, 2060]
  ),
  P(" ", { after: 40 }),
  P("Please fill in the remaining rows with your teammates' names, IDs and the part of Phase 5 each of you worked on before submitting.",
    { italics: true, color: "0F6FAF", size: 19 }),

  makeTable(
    ["Item", "Detail"],
    [
      ["Live website", URL],
      ["Hosting", "Microsoft Azure App Service (Free F1), Canada Central"],
      ["Subscription", "Azure for Students"],
      ["Deployed on", "19 August 2026"],
      ["Demo login for marking", "username: demo    password: puck1234"],
      ["Source code", "GitHub repository (see the deployment record for the structure)"],
    ],
    [2400, 6960]
  ),
  P(" ", { after: 60 }),

  // ---------------- objective ----------------
  H1("2. What Phase 5 asked for, and what we did"),
  P("The instructions for this phase were short: deploy the completed web application to the cloud, write down the steps, and include the website address. We did all of that, and we also fixed something that had been bothering us since Phase 4."),
  P("In Phase 4 our website worked, but every hockey number in it was invented. There were eight teams instead of thirty-two, twenty made-up final scores, and win probabilities we had typed in ourselves so the pages looked right. It was a working back end demonstrating real database skills, but it was not really our project — our project is a prediction model, and none of the model's actual output was on the site."),
  P("So for Phase 5 we set ourselves two goals instead of one:"),
  Bullet("Deploy the site to the cloud, for free, in a way that keeps running by itself."),
  Bullet("Replace every invented number with a real one, so that what visitors see is genuinely what our model predicted."),

  makeTable(
    ["Requirement from the instructions", "Status", "Where to find it"],
    [
      ["Deploy the web application to the cloud", "Done", URL],
      ["Record the deployment steps in a document", "Done", "WinThePuck_Phase5_Deployment_Steps.docx"],
      ["Include the website URL in that document", "Done", "First page, highlighted"],
      ["Team information document", "Done", "This document, section 1"],
      ["Progress report for Phase 5", "Done", "This document, sections 2 to 8"],
    ],
    [4000, 1400, 3960]
  ),
  P(" ", { after: 60 }),

  new Paragraph({ children: [new PageBreak()] }),

  // ---------------- what we built ----------------
  H1("3. What we actually built"),

  H2("The website on Azure"),
  P("A Flask application with seven pages, running on Azure's free tier at " + URL + ". It has:"),
  Bullet("A home page with the model's headline accuracy and a real playoff game replayed second by second, so you can watch the win probability move on every goal and penalty."),
  Bullet("A Games page listing the next 34 NHL games with our model's probability, fair odds and confidence for each one."),
  Bullet("A Matchups page comparing two teams across six season statistics."),
  Bullet("A Results page — the honest scoreboard — showing 1,394 finished games with the probability we gave before each one and whether we were right. The misses are on there too."),
  Bullet("A Leaderboard built from the picks in the database."),
  Bullet("A Discussion section where signed-in members post and like messages."),
  Bullet("Accounts: register, sign in, sign out, with passwords stored as hashes."),

  H2("The prediction service"),
  P("A separate small program that runs once a day on GitHub's free servers. It asks the NHL's public API which games have been played and which are coming, moves every team's Elo rating forward with the real results, recalculates each team's recent form, runs our trained model over the upcoming games, and sends the answers to the website."),
  P("This was the hardest part to design. Our Phase 2 model needs about 127 numbers per game, and many of them (hits, blocked shots, goalie save percentage) only exist in the 18 GB data pipeline. Our solution was to be honest about the split: the numbers the free NHL API can give us — ratings, form, records, rest days, head-to-head — are recalculated for real every single day, and the box-score numbers carry forward from the last full pipeline run. We say so in the code comments rather than pretending everything is live."),

  H2("The leaderboard, without inventing people"),
  P("A brand new website has no members, and a leaderboard with nobody on it looks broken. In Phase 4 we solved that by inventing six members and giving them win totals we made up. We were not comfortable doing that again."),
  P("Instead the leaderboard now has five automatic strategy accounts. Each one follows a fixed rule — always back the model, always back the home team, always back the visitors, back whoever is on the better run, always bet against the model — and each one is scored on the same 82 real playoff games from the 2025-26 season, against the real results. Nothing is typed in. The numbers came out like this:"),
  makeTable(
    ["Strategy", "Correct", "Accuracy", "Points"],
    [
      ["ModelFollower — always backs our model", "49 / 82", "59.8%", "5,230"],
      ["FormChaser — backs the team on the better run", "49 / 82", "59.8%", "5,230"],
      ["RoadWarrior — always backs the visiting team", "43 / 82", "52.4%", "4,690"],
      ["HomeIceFan — always backs the home team", "39 / 82", "47.6%", "4,330"],
      ["Contrarian — always bets against our model", "33 / 82", "40.2%", "3,790"],
    ],
    [4600, 1500, 1600, 1660]
  ),
  P(" ", { after: 40 }),
  P("We like this a lot more than made-up members, because it is actually an experiment. It shows our model beating simple rules of thumb over a real playoff run, and it shows home ice advantage doing worse than a coin flip in those particular playoffs, which surprised us.", { color: "5A6472" }),

  new Paragraph({ children: [new PageBreak()] }),

  // ---------------- work breakdown ----------------
  H1("4. How the work was divided"),
  P("Fill in the names against each area of work before submitting. The areas below are the real chunks of Phase 5.", { italics: true, color: "0F6FAF", size: 19 }),
  makeTable(
    ["Area of work", "Who did it", "Roughly how long"],
    [
      ["Azure setup: subscription, resource group, App Service plan, web app", BLANK, "2 hours"],
      ["Rewriting the database schema and the data importer for real data", BLANK, "5 hours"],
      ["Building the prediction service and the daily refresh job", BLANK, "7 hours"],
      ["Updating the pages: real logos, the new Results page, empty states", BLANK, "4 hours"],
      ["Security: CSRF tokens, secrets in environment variables, cookie flags", BLANK, "2 hours"],
      ["GitHub Actions for deployment and the daily refresh", BLANK, "3 hours"],
      ["Testing the deployed site end to end", BLANK, "2 hours"],
      ["These two documents", BLANK, "3 hours"],
    ],
    [4800, 2600, 1960]
  ),
  P(" ", { after: 60 }),

  // ---------------- decisions ----------------
  H1("5. Decisions we had to make"),
  makeTable(
    ["Decision", "What we chose", "Why"],
    [
      ["Which cloud", "Microsoft Azure", "It is what the course provides student credit for, and App Service has a genuinely free tier rather than a trial."],
      ["Where the model runs", "Not on the web server", "Loading pandas and scikit-learn on every visit would be slow and would eat the free tier's daily processor allowance. Predicting once a day is enough."],
      ["Which database", "SQLite in Azure's /home folder", "A managed database server costs money every month. Our site has a handful of tables and one server, which is exactly what SQLite is good at."],
      ["Where the scheduled job runs", "GitHub Actions", "Azure Functions would have needed a storage account, which is not free. GitHub gives 2,000 minutes a month and we use about 15."],
      ["Whether to keep the demo members", "Replaced with strategy back-tests", "Invented win records are not data. Five fixed rules scored on real games are, and they make the leaderboard mean something."],
      ["Team crests", "Loaded from the NHL's own image server", "They are the real crests, they cost us nothing to host, and the coloured circle underneath still shows if the image cannot load."],
    ],
    [2200, 2600, 4560]
  ),
  P(" ", { after: 60 }),

  new Paragraph({ children: [new PageBreak()] }),

  // ---------------- challenges ----------------
  H1("6. Problems and how we got past them"),

  H2("The season had not started"),
  P("We deployed in the middle of August. There is no hockey in August, so at first the Games page was completely empty, which is a bad look for a prediction site. Then we found that the NHL had already published the 2026-27 schedule, so our model could predict the opening games for real. We also loaded the entire finished 2025-26 season, which gave the Results page 1,394 real games to show. The site now has plenty to look at in the off-season, and it will fill up with live fixtures on its own when the season starts on 29 September."),

  H2("Making the database survive deployments"),
  P("Our first deployment worked, and our second one deleted every account on the site. Azure replaces the whole code folder each time you deploy, and our database file was sitting inside it. Moving it to /home/data — a folder Azure keeps between deployments — fixed it permanently. We tested this properly afterwards by deploying again and checking that a comment posted before the deployment was still there."),

  H2("Two workers, one database"),
  P("Azure runs two copies of our app for reliability. Both of them started up, both saw there was no database, and both started creating one. We now use a lock file: whichever copy gets there first does the work, and the other waits."),

  H2("Deployment from GitHub was blocked"),
  P("Microsoft has started switching off password-based deployment on new accounts by default, which is good security but meant our GitHub workflow could not connect. We turned it back on for this single app with one command, and stored the credentials as a GitHub secret rather than in the code."),

  H2("Knowing which numbers we could honestly refresh"),
  P("This was the interesting one. It would have been easy to have the daily job carry forward last season's numbers and pretend they were current. We went through the model's 127 inputs one at a time and sorted them into what the free NHL API can genuinely tell us and what it cannot, then wrote the refresh job to recalculate the first group properly and be explicit in the code about the second. It took longer, but we can now defend every number on the site."),

  // ---------------- testing ----------------
  H1("7. Testing"),
  P("We tested against the live address rather than our laptops, because a thing that works locally and not in the cloud is exactly the failure Phase 5 is about."),
  makeTable(
    ["Test", "Result"],
    [
      ["All eight pages load over HTTPS", "Pass — all 200, under 0.7 seconds each"],
      ["Register a new account", "Pass"],
      ["Sign in and sign out", "Pass"],
      ["Save a pick on a game, then change it", "Pass"],
      ["Post a comment and like one", "Pass"],
      ["Form with a wrong CSRF token", "Pass — rejected with 400"],
      ["Refresh address with no token / a wrong token", "Pass — both rejected with 401"],
      ["Refresh with the correct token", "Pass — 32 teams and 34 predictions saved"],
      ["Members and comments survive a redeployment", "Pass"],
      ["Unknown address", "Pass — our own 404 page"],
    ],
    [5200, 4160]
  ),
  P(" ", { after: 60 }),

  // ---------------- honest ----------------
  H1("8. What we would tell a marker to look at critically"),
  P("Two things we want to be upfront about, because they are limitations rather than features."),
  Bullet("Some of the model's inputs are carried forward. Roughly a third of the 127 inputs need full box scores, which need the 18 GB pipeline, which cannot run in the cloud. Those inputs hold their last known value between pipeline runs. The strongest inputs — Elo, recent form, records, rest — are recalculated every day from real results."),
  Bullet("Early-season predictions will be the model's weakest. In October the teams have barely played, so the model is leaning mostly on Elo ratings carried over from last season. That is the honest situation for any hockey model in October, and the confidence figures on the site reflect it."),
  P("And one number we want to defend rather than apologise for: our model is right 58.6% of the time. That sounds low until you know that published research puts the ceiling for single-game NHL prediction at about 62%, and that professional bookmakers land around 59-60%. Hockey is a low-scoring sport where one deflection decides a game. On the games our model is most confident about, it is right 65.4% of the time, and that gap is the useful part."),

  // ---------------- learned ----------------
  H1("9. What we learned"),
  Bullet("Deploying is not uploading. Almost everything we had to change — secrets in environment variables, a database that builds itself, storage that survives a redeployment, two workers starting at once — was invisible while the site only ever ran on one laptop."),
  Bullet("Writing the deployment down as commands instead of screenshots made it repeatable. We tore the whole thing down and rebuilt it once, just to check, and it took five minutes."),
  Bullet("Free tiers have real edges, and designing around them is a skill. Keeping the machine learning off the web server was not a compromise — it made the site faster and is how this is done properly."),
  Bullet("Filling a page with invented data is easy and it hides whether the real thing works. Every time we replaced fake data with real data we found a bug: a column that was an integer and needed decimals, a team the pipeline knew about but the API did not, a season that had not started yet."),

  // ---------------- next ----------------
  H1("10. Where the project stands"),
  P("Phase 5 is complete. The website is live, it holds real data, it refreshes itself every morning, and it costs nothing to run. The whole project — all five phases — is organised and ready to be published to GitHub."),
  P("If we carried on, the next things we would do are: run the Phase 1 pipeline again once the new season is a month old so the box-score inputs are fresh; show each prediction's biggest reasons so visitors can see why the model likes a team; and add a page tracking how the model does during the 2026-27 season as it happens, rather than only in the walk-forward test."),

  Rule(),
  P("WinThePuck · Project Phase 5 · Team & Progress Report · " + URL,
    { size: 17, color: "5A6472", align: AlignmentType.CENTER, after: 0 }),
];

const doc = new Document({
  creator: "WinThePuck team",
  title: "WinThePuck — Phase 5 Team and Progress Report",
  description: "Team information and the Phase 5 progress report for the WinThePuck project.",
  numbering,
  styles: { default: { document: { run: { font: "Calibri", size: 21, color: "1B2430" } } } },
  sections: [{ properties: sectionProps, children: body }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("WinThePuck_Phase5_Report.docx", buf);
  console.log("wrote WinThePuck_Phase5_Report.docx", buf.length, "bytes");
});
