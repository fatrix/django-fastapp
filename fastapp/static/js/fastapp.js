/*Pusher.log = function(message) {
  if (window.console && window.console.log) {
    console.log(message);
  }
};*/

// initialize Pusher listener
var pusher = new Pusher(window.pusher_key);
var channel = pusher.subscribe(window.username);
channel.bind('console_msg', function(data) {
    data.source = "Server";
    add_message(data);
});
channel.bind('pusher:subscription_succeeded', function() {
    add_client_message("Subscription succeeded.");
});

function add_client_message(message) {
    data = {};
    data.message = message;
    var now = NDateTime.Now();
    data.datetime = now.ToString("yyyy-MM-dd HH:mm:ss.ffffff");
    data.class = "info";
    data.source = "Client";
    add_message(data);
}

function add_message(data) {
    $("div#messages").prepend("<p class='"+data.class+"'>"+data.datetime+" : "+data.source+" : "+data.message+"</p>");
    $("div#messages p").slice(10).remove();
}

//function send_me(broadcast_message, cb, arg) {
//    $.post("/fastapi/"+window.active_base+"/message/", {'message': broadcast_message}, function(data) {
//        cb(arg);
//      });
//}

function redirect(location) {
    window.location = location;
}


$(function() {
    // edit
    $("button#edit_html").click(function(event) {
       event.preventDefault();
       $("form#edit_html").find("div.CodeMirror").toggle();
    });

    // shared
    $("button#share").click(function(event) {
      event.preventDefault();
      add_client_message('Access the shared base: <a href="'+window.shared_key_link+'">'+ window.shared_key_link+'</a>');
    });
    

    // exec
    $("a.exec").click(function(event) {
       event.preventDefault();
       var url = $(this).attr('href');
       $.get(url, function(data) {
       });
    });

    // forms
    $("form").submit(function(event) {
        console.warn(event.currentTarget.method);
        if (event.currentTarget.method == "post") {
            $.post(event.currentTarget.action, $(this).serialize(), function(data){
              console.log("send form with POST");
              console.log(data);
            });
        } else if (event.currentTarget.method == "get") {
            $.get(event.currentTarget.action, $(this).serialize(), function(data){
                //if (data.redirect) {
                //  send_me("redirecting browser to: "+data.redirect, redirect, data.redirect)
                //}
                redirect(data.redirect);

            });

                     } else {
            console.error("no method defined on form");
        }
        event.preventDefault();
        return false;

    });
});

