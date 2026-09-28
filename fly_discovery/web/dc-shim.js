/* dc-shim.js — Design Component 템플릿을 브라우저에서 바로 돌리는 최소 런타임.
   지원: {{ 경로 }} (텍스트/속성), <sc-for list as>, <sc-if value>, onClick, ref.
   아티팩트 런타임의 부분집합이라, 이 파일로 고친 내용을 다시 아티팩트에 붙일 수 있다. */
(function (global) {
  'use strict';

  function lookup(scope, path) {
    if (path === 'true') return true;
    if (path === 'false') return false;
    var cur = scope, parts = String(path).trim().split('.');
    for (var i = 0; i < parts.length; i++) {
      if (cur === null || cur === undefined) return undefined;
      cur = cur[parts[i]];
    }
    return cur;
  }

  var HOLE = /\{\{([^}]+)\}\}/g;

  function interp(text, scope) {
    return text.replace(HOLE, function (_, p) {
      var v = lookup(scope, p);
      return v === undefined || v === null ? '' : String(v);
    });
  }

  function wholeHole(value) {
    var m = /^\s*\{\{([^}]+)\}\}\s*$/.exec(value);
    return m ? m[1].trim() : null;
  }

  function render(node, scope, out) {
    if (node.nodeType === 3) {
      var t = node.nodeValue;
      if (t.indexOf('{{') >= 0) out.appendChild(document.createTextNode(interp(t, scope)));
      else out.appendChild(node.cloneNode(false));
      return;
    }
    if (node.nodeType !== 1) return;
    var tag = node.tagName.toLowerCase();

    if (tag === 'sc-for') {
      var listPath = wholeHole(node.getAttribute('list') || '');
      var as = node.getAttribute('as') || 'item';
      var list = listPath ? lookup(scope, listPath) : null;
      if (!Array.isArray(list)) list = [];
      list.forEach(function (item, idx) {
        var child = Object.create(scope);
        child[as] = item;
        child.$index = idx;
        each(node.childNodes, child, out);
      });
      return;
    }

    if (tag === 'sc-if') {
      var condPath = wholeHole(node.getAttribute('value') || '');
      if (condPath && lookup(scope, condPath)) each(node.childNodes, scope, out);
      return;
    }

    var el = document.createElement(tag === 'x-dc' ? 'div' : tag);
    for (var i = 0; i < node.attributes.length; i++) {
      var a = node.attributes[i], name = a.name, val = a.value;
      if (name.indexOf('hint-') === 0) continue;
      var whole = wholeHole(val);
      if (name === 'onclick' || name === 'onClick') {
        if (whole) {
          (function (fnPath) {
            el.addEventListener('click', function (ev) {
              var fn = lookup(scope, fnPath);
              if (typeof fn === 'function') fn(ev);
            });
          })(whole);
        }
        continue;
      }
      if (name === 'ref') {
        if (whole) {
          var fn = lookup(scope, whole);
          if (typeof fn === 'function') queueMicrotask(function () { fn(el); });
        }
        continue;
      }
      el.setAttribute(name, val.indexOf('{{') >= 0 ? interp(val, scope) : val);
    }
    each(node.childNodes, scope, el);
    out.appendChild(el);
  }

  function each(nodes, scope, out) {
    for (var i = 0; i < nodes.length; i++) render(nodes[i], scope, out);
  }

  function DCLogic(props) { this.props = props || {}; this.state = {}; }
  DCLogic.prototype.setState = function (patch) {
    Object.assign(this.state, patch);
    if (this.__host) this.__host.rerender();
  };
  DCLogic.prototype.forceUpdate = function () { if (this.__host) this.__host.rerender(); };
  DCLogic.prototype.renderVals = function () { return {}; };

  function mount(templateEl, Component, mountEl) {
    var inst = new Component({});
    var host = {
      rerender: function () {
        var frag = document.createDocumentFragment();
        each(templateEl.content.childNodes, inst.renderVals(), frag);
        mountEl.textContent = '';
        mountEl.appendChild(frag);
      }
    };
    inst.__host = host;
    host.rerender();
    if (typeof inst.componentDidMount === 'function') inst.componentDidMount();
    global.addEventListener('beforeunload', function () {
      if (typeof inst.componentWillUnmount === 'function') inst.componentWillUnmount();
    });
    return inst;
  }

  global.DCLogic = DCLogic;
  global.dcMount = mount;
})(window);
