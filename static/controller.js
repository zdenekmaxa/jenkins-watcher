var jenkinsWatcher = angular.module('jenkinsWatcher', []);

jenkinsWatcher.controller("mainController", ['$scope', '$http', function($scope, $http)
{
    // number of days to the history, 1 day is defined in html as default
    $scope.daysLimit = [];
    for (i = 2; i <= 15; i++) { $scope.daysLimit.push({value: i}) }
    $scope.daysLimitCurrent = 1;

    // controlling loading spinner via
    // document.getElementById("loadingshadowdivid").className = "hidden"; | "displayed"
    // not successful, via document.readyState also no luck, this angulary way via $scope OK
    $scope.showSpinner = false;

    // test data, development data from <script src="builds.js"></script>
    // $scope.buildsStats = testBuildsStats;

    var getBuildsData = function()
    {
        // url = 'https://jenkins-watcher.appspot.com/builds';
        url = '/builds' + '?days_limit=' + $scope.daysLimitCurrent;
        // console.log("calling URL" + url);
        // turns the spinner on
        $scope.showSpinner = true;

        //var headers = { "Accept": "application/json" };
        //headers["Cache-Control"] = "max-age=0, must-revalidate, private";
        $http.get(url).
            success(function(data, status, headers, config)
            {
                console.log("success, status: " + status);
                $scope.buildsStats = data;
                $scope.showSpinner = false;
            }).
            error(function(data, status, headers, config)
            {
                // if using interval functional to invoke automatically,
                // will have to clear $scope.buildsStats, $scope.myErrorMessage
                // explicitly
                $scope.myErrorMessage = data.message;
                console.log("error occurred: " + $scope.myErrorMessage + " status: " + status);
                $scope.showSpinner = false;
            });
    };

    // called only when the list-box daysLimitSelection selected value changes
    $scope.$watch('daysLimitSelection', function(newValue, oldValue)
    {
        if ($scope.daysLimitSelection != undefined)
        {
            $scope.daysLimitCurrent = $scope.daysLimitSelection.value;
            // console.log(newValue, oldValue);
        }
        else
        {
            $scope.daysLimitCurrent = 1;
        }
        console.log("days_limit value changed to: "  + $scope.daysLimitCurrent);
        getBuildsData();
    });

    // with this call, the function gets called twice (second time from watch)
    // getBuildsData();

    // console.log($scope.buildsStats);

    // $scope.$apply();
    // angujar error message that operation is already in progress
    // should check if data changed (if necessary) and call this apply
    // or have it removed

}]);