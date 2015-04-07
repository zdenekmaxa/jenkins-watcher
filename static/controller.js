var jenkinsWatcher = angular.module('jenkinsWatcher', []);

jenkinsWatcher.controller("mainController", 
        ['$scope', '$http', function($scope, $http)
{
    // test data, development data from <script src="builds.js"></script>
    // test_builds_stats ...
    
    // $scope.builds_stats = test_builds_stats;

    var getBuildsData = function()
    {
        return $http({
            method: 'GET',
            url: 'https://jenkins-watcher.appspot.com/builds'
        });
    };

    getBuildsData().success(function(response)
    {
        $scope.builds_stats = response;
    });

    // console.log($scope.builds_stats);

    // $scope.$apply();
    // angujar error message that operation is already in progress
    // should check if data changed (if necessary) and call this apply
    // or have it removed
 
}]);
