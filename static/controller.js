var jenkinsWatcher = angular.module('jenkinsWatcher', []);

jenkinsWatcher.controller("mainController", ['$scope', '$http', function($scope, $http)
{
    // number of days to the history
    // $scope.daysLimit = [1, 2, 3, 4, 5];
    $scope.daysLimit = [ {day: 1}, {day: 2}, {day: 3}, {day: 4}, {day: 5} ];

    console.log($scope.daysLimit);

    // test data, development data from <script src="builds.js"></script>
    // $scope.buildsStats = testBuildsStats;

    var getBuildsData = function()
    {
        $http.get('https://jenkins-watcher.appspot.com/builds').
            success(function(data, status, headers, config)
            {
                console.log("success, status: " + status);
                $scope.buildsStats = data;
            }).
            error(function(data, status, headers, config)
            {
                // if using interval functional to invoke automatically,
                // will have to clear $scope.buildsStats, $scope.myErrorMessage
                // explicitly
                $scope.myErrorMessage = data.message;
                console.log("error occurred: " + $scope.myErrorMessage + " status: " + status);
            });
    };

    getBuildsData();

    // console.log($scope.buildsStats);

    // $scope.$apply();
    // angujar error message that operation is already in progress
    // should check if data changed (if necessary) and call this apply
    // or have it removed
 
}]);