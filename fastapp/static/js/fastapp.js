// Enable pusher logging - don't include this in production
Pusher.log = function(message) {
  if (window.console && window.console.log) {
    console.log(message);
  }
};

function add_client_message(message) {
    data = {};
    data.message = message;
    var now = NDateTime.Now();
    data.datetime = now.ToString("yyyy-MM-dd HH:mm:ss.ffffff");
    data.class = "info";
    data.source = "Client";
    console.log(data);
    add_message(data);
}


function add_message(data) {
    $("div#messages").prepend("<p class='"+data.class+"'>"+data.datetime+" : "+data.source+" : "+data.message+"</p>");
    $("div#messages p").slice(10).remove();
}

var pusher = new Pusher('2e734d324cc771f7c915');
var channel = pusher.subscribe(window.username);
channel.bind('console_msg', function(data) {
    data.source = "Server";
    add_message(data);
});
channel.bind('pusher:subscription_succeeded', function() {
    add_client_message("Subscription succeeded.");
});

$(function() {
    // exec
    $("a.exec").click(function(event) {
       event.preventDefault(); 

       var url = $(this).attr('href');
       $.get(url, function(data) {
         //alert(data);
       });

    });

    // forms
    $("form").submit(function(event) {
        console.warn(event.currentTarget.method);
        if (event.currentTarget.method == "post") {
            $.post(event.currentTarget.action, $(this).serialize(), function(data){/*aaa*/});
        } else if (event.currentTarget.method == "get") {
            $.get(event.currentTarget.action, $(this).serialize(), function(data){/*aaa*/});
        } else {
            console.error("no method defined on form");
        }
        event.preventDefault;
        return false;

    });
});