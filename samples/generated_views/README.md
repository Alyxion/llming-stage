# Generated views

Two routes created with `@stage.view(...)`. The decorated functions
return `VueResponse` objects, which is useful for tiny generated pages
or examples where a separate Vue file would hide the point. One route
returns an inline template; the other keeps the template inline and
loads the Vue script from a relative `status.js` file.
