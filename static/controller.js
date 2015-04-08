var jenkinsWatcher = angular.module('jenkinsWatcher', []);

jenkinsWatcher.controller("mainController", ['$scope', '$http', function($scope, $http)
{
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
                console.log("error occurred: " + data.message + " status: " + status);
                $scope.myErrorMessage = data.message;
            });
    };

    getBuildsData();

    console.log("message: " + $scope.myErrorMessage);

    // console.log($scope.buildsStats);

    // $scope.$apply();
    // angujar error message that operation is already in progress
    // should check if data changed (if necessary) and call this apply
    // or have it removed
 
}]);