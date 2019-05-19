var baseUrlVvzUzh = 'https://studentservices.uzh.ch/uzh/anonym/vvz/index.html#/details/'
var apiUrl = 'https://greenvvz.ifi.uzh.ch/'

$(document).ready(function () {
    //https://studentservices.uzh.ch/uzh/anonym/vvz/index.html#/details/2017/004/SM/50825256
    var root = $('#anchor-public')
    if(root.data("lang") === 'en'){
        var langTitle = 'UZH Courses related to sustainability';
        var langName = 'Name of the course';
        var langSemester = '(FS = Spring Semester, HS=Fall Semester)'
    } else {
        var langTitle = 'Lehrveranstaltungen der UZH mit Nachhaltigkeitsbezug';
        var langName = 'Name der Lehrveranstaltung';
        var langSemester = '(FS = Frühjahressemester, HS = Herbstsemester)'
    }


    $.ajax({
        url : apiUrl+"/modules/whitelist",
        method : 'GET',
        success : function (data) {
            console.log(data)
            var table = $("<table></table>")
            table.append('<thead><th colspan="2"><strong>'+langTitle+'</strong></th></thead>')
            var body = $('<tbody id="whitelist_body"></tbody>')
            body.append('<tr><td><strong>'+langName+'</strong></td><td><strong>Semester</strong><br><p>'+langSemester+'</p></td></tr>')
            for (var row in data){
                var url = baseUrlVvzUzh+data[row].PiqYear+'/'+data[row].PiqSession+'/SM/'+data[row].SmObjId
                var module = $(`<tr id="${data[row].id}" data-SmObjId="data[row].SmObjId" data-semester="${data[row].PiqYear} ${data[row].PiqSession}"><td><a href="${url}">${data[row].title}</a></td><td><span class="semester">HS </span>${data[row].PiqYear % 100}</td></tr>`)
                body.append(module)
            }
            table.append(body)
            root.append(table)
        },
        error : function (err) {
            console.log(err)
        }
    })
});