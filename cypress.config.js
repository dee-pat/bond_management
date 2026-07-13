const path = require("path");

module.exports = {
	adminPassword: "admin",
	testUser: "frappe@example.com",
	defaultCommandTimeout: 20000,
	pageLoadTimeout: 30000,
	viewportHeight: 960,
	viewportWidth: 1400,
	video: true,
	videosFolder: path.resolve(__dirname, "..", "..", "cypressVideos"),
	retries: {
		runMode: 1,
		openMode: 0,
	},
	e2e: {
		baseUrl: "http://test_site:8000",
		specPattern: "cypress/integration/**/*.js",
		supportFile: "cypress/support/e2e.js",
	},
};
