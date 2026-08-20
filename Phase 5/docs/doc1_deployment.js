const K = require("./build_docs.js");
const { P, Rich, H1, H2, Bullet, Code, Rule, makeTable, titleBlock,
        Document, Packer, Paragraph, TextRun, AlignmentType,
        ExternalHyperlink, PageBreak, numbering, sectionProps, fs } = K;

const URL = "https://winthepuck.azurewebsites.net";

const body = [
  ...titleBlock(
    "Project Phase 5 · Cloud Deployment",
    "WinThePuck — Deployment Record",
    "How we put our NHL prediction website on Microsoft Azure, written down step by step so anybody could follow it again."
  ),

  // ---------------- the URL ----------------
  new Paragraph({
    spacing: { before: 60, after: 60 },
    shading: { type: K.ShadingType.CLEAR, fill: "E8F3FB" },
    border: {
      top:    { style: K.BorderStyle.SINGLE, size: 6, color: "9FC9E4" },
      bottom: { style: K.BorderStyle.SINGLE, size: 6, color: "9FC9E4" },
      left:   { style: K.BorderStyle.SINGLE, size: 24, color: "0F6FAF" },
      right:  { style: K.BorderStyle.SINGLE, size: 6, color: "9FC9E4" },
    },
    indent: { left: 200, right: 200 },
    children: [
      new TextRun({ text: "The live website", bold: true, size: 20, color: "0F6FAF", font: "Calibri" }),
      new TextRun({ break: 1 }),
      new TextRun({ text: " " }),
    ],
  }),
  new Paragraph({
    spacing: { after: 240 },
    shading: { type: K.ShadingType.CLEAR, fill: "E8F3FB" },
    border: {
      bottom: { style: K.BorderStyle.SINGLE, size: 6, color: "9FC9E4" },
      left:   { style: K.BorderStyle.SINGLE, size: 24, color: "0F6FAF" },
      right:  { style: K.BorderStyle.SINGLE, size: 6, color: "9FC9E4" },
    },
    indent: { left: 200, right: 200 },
    children: [
      new ExternalHyperlink({
        link: URL,
        children: [new TextRun({ text: URL, size: 26, bold: true, color: "0F6FAF",
                                 underline: {}, font: "Calibri" })],
      }),
      new TextRun({ break: 1 }),
      new TextRun({ text: "Deployed 19 August 2026 · Microsoft Azure App Service (Free F1) · Canada Central",
                    size: 18, color: "5A6472", font: "Calibri" }),
    ],
  }),

  // ---------------- 1 ----------------
  H1("1. What we put in the cloud"),
  P("Our website is a Flask application. It shows the games coming up in the NHL, the probability our model gives each team, and a leaderboard built from the picks our members make. Visitors can create an account, sign in, save a pick on any game, and talk about it in the discussion section."),
  P("The one thing we could not put in the cloud is our data. Phase 1 downloads about 18 GB of play-by-play and shift chart data from the NHL, and Phase 2 trains three machine learning models on top of it. Nothing that big or that slow belongs on a free web server."),
  P("So we split the project in two:"),
  Bullet("The website is small. It only needs Flask, Werkzeug and gunicorn, which is why it fits comfortably in Azure's free tier and starts in a couple of seconds."),
  Bullet("The model runs separately, once a day, on a GitHub Actions runner. It works out the predictions and sends them to the website over a protected web address. The website just stores them and shows them."),
  P("This is a normal pattern in industry — it is called batch prediction. The slow, expensive part happens on a schedule, and the fast part is all the website has to do when somebody visits.", { italics: true, color: "5A6472" }),

  H2("The pieces, and who does what"),
  makeTable(
    ["Piece", "Where it runs", "What it is responsible for"],
    [
      ["WinThePuck website", "Azure App Service (Free F1)", "Every page, the accounts, the picks, the comments, the leaderboard."],
      ["SQLite database", "Azure, in the /home folder", "Members, their picks, their comments, the teams and the games."],
      ["Prediction refresh", "GitHub Actions (free runner)", "Runs the trained model every morning and sends new predictions to the site."],
      ["Automatic deploy", "GitHub Actions (free runner)", "Pushes the website to Azure whenever we change it on the main branch."],
      ["NHL public API", "api-web.nhle.com", "Schedules, scores, standings and team season stats. Free, no key needed."],
    ],
    [2100, 2600, 4660]
  ),
  P(" ", { after: 60 }),

  // ---------------- 2 ----------------
  H1("2. Why we chose these Azure services"),
  P("Our budget was zero. We have $100 of Azure for Students credit, but we wanted to finish the project without spending any of it, so that the site keeps running after the credit runs out. Everything below is on a free tier."),
  makeTable(
    ["Service", "Tier we picked", "What it costs us", "Why"],
    [
      ["App Service Plan", "F1 (Free), Linux", "$0.00 / month", "Free forever, not a trial. Enough for a class project."],
      ["Web App", "Python 3.12 on Linux", "$0.00 / month", "Runs Flask through gunicorn. Comes with a free HTTPS certificate."],
      ["Database", "SQLite file in /home", "$0.00 / month", "A managed database server would cost money. Our site is small, and Azure's /home folder survives restarts."],
      ["Scheduled job", "GitHub Actions", "$0.00 / month", "Azure Functions would need a paid storage account. GitHub gives us 2,000 free minutes a month and we use about 15."],
    ],
    [1900, 1900, 1700, 3860]
  ),
  P(" ", { after: 60 }),
  P("What we gave up by staying free: the free tier has no \"Always On\", so if nobody visits for 20 minutes the site goes to sleep and the next visitor waits a few extra seconds. It also has a limit of 60 minutes of processor time a day. For a project like ours neither of those matters.", { color: "5A6472" }),

  new Paragraph({ children: [new PageBreak()] }),

  // ---------------- 3 ----------------
  H1("3. What we changed in the code before deploying"),
  P("We could not simply upload the Phase 4 project. Four things had to change first."),

  H2("a) We replaced all of the made-up data with real data"),
  P("In Phase 4 the teams, the games, the scores and the win probabilities were all typed into seed_data.py by hand — eight teams and twenty invented results, just so the pages had something to show. For Phase 5 every one of those numbers now comes from somewhere real:"),
  makeTable(
    ["What you see on the site", "Where it really comes from"],
    [
      ["All 32 teams, their records, streaks, goals, power play, penalty kill, faceoff %", "The NHL's own statistics API"],
      ["The upcoming schedule and start times", "The NHL's published 2026-27 schedule"],
      ["Every win probability and confidence figure", "Our Phase 2 ensemble model"],
      ["1,394 finished games with the probability given before each one", "Our Phase 2 walk-forward test"],
      ["The play-by-play replay on the home page", "A real 2026 Stanley Cup Final game through our live model"],
      ["The five strategy accounts on the leaderboard", "Real back-tests on real playoff games"],
    ],
    [4300, 5060]
  ),
  P(" ", { after: 60 }),

  H2("b) Secrets moved out of the code"),
  P("Phase 4 had the Flask secret key written straight into app.py. Anybody who read our GitHub repository could have forged a login cookie. Now the key is read from an environment variable that only exists inside Azure."),

  H2("c) The database had to build itself"),
  P("On a laptop you run seed_data.py by hand before starting the site. In the cloud there is nobody to do that. So the website now checks on start-up whether the database exists, and if it does not, it builds it from the JSON files we ship with the app. Because Azure starts two copies of our app at once, we added a small lock file so they do not both try to build it at the same time."),

  H2("d) We added protection we did not have before"),
  Bullet("Every form now carries a CSRF token, so another website cannot make your browser post a comment or a pick without you knowing."),
  Bullet("The login cookie is marked HttpOnly, SameSite and Secure, so JavaScript cannot read it and it is only ever sent over HTTPS."),
  Bullet("The refresh address is protected by a bearer token, so nobody can push fake predictions into the site."),
  Bullet("The whole site is HTTPS only — Azure redirects plain HTTP automatically."),

  new Paragraph({ children: [new PageBreak()] }),

  // ---------------- 4 ----------------
  H1("4. The deployment, step by step"),
  P("Everything below was done from the Terminal on a Mac using the Azure CLI. We chose the command line over the Azure Portal on purpose: the commands are the record. Anybody can copy them and get exactly the same result, which is not true of a list of buttons to click."),

  H2("Step 1 — Install the Azure CLI and sign in"),
  Code([
    "brew install azure-cli",
    "az login",
    "az account show --output table",
  ]),
  P("az login opens a browser window. We signed in with the SAIT student account, and az account show confirmed we were on the \"Azure for Students\" subscription."),

  H2("Step 2 — Make a resource group"),
  P("A resource group is just a folder in Azure. Putting everything for one project in one group means we can delete the whole thing later with a single command. We picked Canada Central because it is the closest region to Calgary, so pages load a little faster for us."),
  Code(["az group create \\", "  --name rg-winthepuck \\", "  --location canadacentral"]),

  H2("Step 3 — Create the App Service plan on the free tier"),
  P("The plan is the server our site sits on. This is the command where the money is decided, so it is the one we double-checked: --sku F1 is the free tier."),
  Code([
    "az appservice plan create \\",
    "  --name plan-winthepuck \\",
    "  --resource-group rg-winthepuck \\",
    "  --location canadacentral \\",
    "  --is-linux \\",
    "  --sku F1",
  ]),

  H2("Step 4 — Create the web app itself"),
  P("The name has to be unique across the whole of Azure, because it becomes the web address. We were lucky that winthepuck was free."),
  Code([
    "az webapp create \\",
    "  --name winthepuck \\",
    "  --resource-group rg-winthepuck \\",
    "  --plan plan-winthepuck \\",
    "  --runtime \"PYTHON:3.12\"",
  ]),
  P("Azure immediately gave us the address https://winthepuck.azurewebsites.net, with an HTTPS certificate already set up."),

  H2("Step 5 — Add the settings and the secrets"),
  P("These become environment variables inside the app. We generated both secrets with Python's secrets module and never typed them into a file that goes to GitHub."),
  Code([
    "az webapp config appsettings set \\",
    "  --name winthepuck --resource-group rg-winthepuck \\",
    "  --settings SECRET_KEY=\"<64 random characters>\" \\",
    "             REFRESH_TOKEN=\"<43 random characters>\" \\",
    "             SCM_DO_BUILD_DURING_DEPLOYMENT=true \\",
    "             WEBSITES_CONTAINER_START_TIME_LIMIT=300 \\",
    "             PYTHONUNBUFFERED=1",
  ]),
  makeTable(
    ["Setting", "What it does"],
    [
      ["SECRET_KEY", "Signs the cookie that keeps members logged in."],
      ["REFRESH_TOKEN", "The password the daily prediction job uses to prove who it is."],
      ["SCM_DO_BUILD_DURING_DEPLOYMENT", "Tells Azure to run pip install on our requirements.txt after each upload."],
      ["WEBSITES_CONTAINER_START_TIME_LIMIT", "Gives the app 5 minutes to start, because the very first start builds the database."],
      ["PYTHONUNBUFFERED", "Makes Python print its log messages straight away instead of holding them back."],
    ],
    [3400, 5960]
  ),
  P(" ", { after: 60 }),

  H2("Step 6 — Tell Azure how to start the site"),
  P("Flask's built-in server is only meant for development. In the cloud we use gunicorn, which is a proper production web server. Our startup.sh starts it with two worker processes."),
  Code([
    "az webapp config set \\",
    "  --name winthepuck --resource-group rg-winthepuck \\",
    "  --startup-file \"startup.sh\"",
  ]),

  H2("Step 7 — Force HTTPS"),
  Code([
    "az webapp update \\",
    "  --name winthepuck --resource-group rg-winthepuck \\",
    "  --https-only true",
  ]),

  H2("Step 8 — Upload the website"),
  Code([
    "cd \"Phase 5/winthepuck-cloud\"",
    "zip -r ../winthepuck.zip . -x \"instance/*\" \"__pycache__/*\"",
    "az webapp deploy \\",
    "  --name winthepuck --resource-group rg-winthepuck \\",
    "  --src-path ../winthepuck.zip --type zip",
  ]),
  P("Azure unpacked the zip, ran pip install on our requirements.txt, and started gunicorn. It reported RuntimeSuccessful, and the first request to the site built the database from the JSON files inside the package."),

  H2("Step 9 — Check that it really works"),
  Code([
    "curl https://winthepuck.azurewebsites.net/healthz",
    "",
    "{\"games\":1428,\"status\":\"ok\",\"teams\":32,",
    " \"lastRefresh\":\"2026-08-20T04:06:36+00:00\"}",
  ]),
  P("We wrote /healthz on purpose. It is a tiny page that counts the rows in the database, so one request tells us both that the site is alive and that its data arrived safely."),

  H2("Step 10 — Connect the daily prediction job"),
  P("This is the step that makes the site stay correct instead of slowly going stale. We ran the refresh by hand first, to prove the whole chain works end to end:"),
  Code([
    "cd \"Phase 5/model-service\"",
    "python3 refresh_predictions.py \\",
    "  --days-ahead 30 \\",
    "  --post https://winthepuck.azurewebsites.net \\",
    "  --token \"$REFRESH_TOKEN\"",
    "",
    "website replied 200: {\"status\":\"ok\",\"teams\":32,",
    "  \"predictions\":34,\"results\":0,\"picksScored\":0}",
  ]),
  P("Then we put the same command in a GitHub Actions workflow that runs at 11:30 UTC every day, which is early morning in Calgary — after every NHL game has finished and before anybody looks at the site."),

  H2("Step 11 — Automatic deployment from GitHub"),
  P("Finally we set up a second workflow so that pushing a change to the main branch deploys it. It installs our requirements, checks the app imports without errors, uploads it to Azure, and then calls /healthz to make sure the site came back up. If the site does not answer, the workflow fails and we know straight away."),
  Code([
    "az webapp deployment list-publishing-profiles \\",
    "  --name winthepuck --resource-group rg-winthepuck --xml",
  ]),
  P("The XML this prints is stored in GitHub as a repository secret called AZURE_WEBAPP_PUBLISH_PROFILE. It is a password, so it lives in GitHub's secret store and never in the code."),

  new Paragraph({ children: [new PageBreak()] }),

  // ---------------- 5 ----------------
  H1("5. How we tested the deployed site"),
  P("We tested the site on the real address, not on our laptops, because the whole point of this phase was to prove it works in the cloud."),
  makeTable(
    ["What we tested", "How", "Result"],
    [
      ["Every page loads", "Requested all 8 pages over HTTPS", "All returned 200, under 0.7 seconds"],
      ["A page that does not exist", "Requested /nope", "404 with our own error page"],
      ["Creating an account", "Registered a new member through the form", "Account created and signed in"],
      ["Signing in", "Signed in as the demo account", "Signed in, name shown in the navigation bar"],
      ["Saving a pick", "Picked a team on an upcoming game", "Pick saved and shown as selected"],
      ["Posting a comment", "Posted in the discussion", "Comment appeared straight away"],
      ["CSRF protection", "Posted a form with a wrong token", "Rejected with 400, as designed"],
      ["Refresh security", "Posted to the refresh address with no token, then a wrong one", "Both rejected with 401"],
      ["Refresh works", "Posted with the correct token", "200, 32 teams and 34 predictions saved"],
      ["Data survives a restart", "Restarted the app and checked /healthz", "Same members, picks and comments still there"],
    ],
    [2700, 3600, 3060]
  ),
  P(" ", { after: 60 }),

  // ---------------- 6 ----------------
  H1("6. Problems we ran into, and how we fixed them"),

  H2("The database kept disappearing"),
  P("Our first idea was to keep the SQLite file next to the code. That works on a laptop, but on Azure every deployment replaces the code folder, so every deployment would have wiped out our members and their comments. We moved the database to /home/data, which is a folder Azure keeps between restarts and deployments."),

  H2("Two copies of the app fighting over the same database"),
  P("gunicorn starts two worker processes. Both of them noticed there was no database and both started building one. We fixed it with a lock file: the first worker to create it does the building, and the second one simply waits until the tables appear."),

  H2("GitHub could not deploy at first"),
  P("Our first attempt at automatic deployment failed with an authentication error. Newer Azure accounts have basic authentication for deployments switched off by default, which is a sensible security default. We turned it back on for this one app so that GitHub Actions could use the publish profile."),
  Code([
    "az resource update --resource-group rg-winthepuck \\",
    "  --name scm --namespace Microsoft.Web \\",
    "  --resource-type basicPublishingCredentialsPolicies \\",
    "  --parent sites/winthepuck --set properties.allow=true",
  ]),

  H2("It is the off-season"),
  P("We deployed in August, when the NHL season has not started. That is genuinely awkward for a prediction site: there are no games being played to predict. Two things saved us. First, the NHL had already published the 2026-27 schedule, so the model could predict the opening 34 games for real. Second, we loaded the whole finished 2025-26 season into the site so that the Results page has 1,394 real games to show, each with the probability the model gave it before it was played."),

  // ---------------- 7 ----------------
  H1("7. What it costs"),
  P("Nothing. We checked twice — once by reading the pricing tier back out of Azure, and once by listing everything in the subscription to make sure we had not accidentally created something billable."),
  Code([
    "az appservice plan show --name plan-winthepuck \\",
    "  --resource-group rg-winthepuck \\",
    "  --query \"{sku:sku.name,tier:sku.tier}\" -o table",
    "",
    "Sku    Tier",
    "-----  ------",
    "F1     Free",
  ]),
  P("The subscription contains exactly two resources — the free plan and the web app that sits on it. There is no storage account, no database server and no static IP address. Our $100 of student credit is untouched."),

  // ---------------- 8 ----------------
  H1("8. Doing it all again from scratch"),
  P("If the site ever had to be rebuilt, these are the only commands needed. They take about five minutes."),
  Code([
    "az group create --name rg-winthepuck --location canadacentral",
    "",
    "az appservice plan create --name plan-winthepuck \\",
    "  --resource-group rg-winthepuck --is-linux --sku F1",
    "",
    "az webapp create --name winthepuck --resource-group rg-winthepuck \\",
    "  --plan plan-winthepuck --runtime \"PYTHON:3.12\"",
    "",
    "az webapp config appsettings set --name winthepuck \\",
    "  --resource-group rg-winthepuck \\",
    "  --settings SECRET_KEY=\"...\" REFRESH_TOKEN=\"...\" \\",
    "             SCM_DO_BUILD_DURING_DEPLOYMENT=true",
    "",
    "az webapp config set --name winthepuck \\",
    "  --resource-group rg-winthepuck --startup-file \"startup.sh\"",
    "",
    "az webapp update --name winthepuck \\",
    "  --resource-group rg-winthepuck --https-only true",
    "",
    "az webapp deploy --name winthepuck --resource-group rg-winthepuck \\",
    "  --src-path winthepuck.zip --type zip",
  ]),
  P("And to remove everything and stop any possibility of a charge:"),
  Code(["az group delete --name rg-winthepuck --yes"]),

  Rule(),
  P("WinThePuck · Project Phase 5 · Cloud Deployment · " + URL,
    { size: 17, color: "5A6472", align: AlignmentType.CENTER, after: 0 }),
];

const doc = new Document({
  creator: "WinThePuck team",
  title: "WinThePuck — Phase 5 Deployment Record",
  description: "How the WinThePuck NHL prediction website was deployed to Microsoft Azure.",
  numbering,
  styles: { default: { document: { run: { font: "Calibri", size: 21, color: "1B2430" } } } },
  sections: [{ properties: sectionProps, children: body }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("WinThePuck_Phase5_Deployment_Steps.docx", buf);
  console.log("wrote WinThePuck_Phase5_Deployment_Steps.docx", buf.length, "bytes");
});
