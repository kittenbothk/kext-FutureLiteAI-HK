{
    argsHook: {
      ICON: (txt, args) => {
        return txt.split("").join(',');
      },
      textUnicode: (txt, args) => {
        console.log('textUnicode', txt, args)
        if(args.gen){
          let code = txt
          if((txt.charAt(0) === "'" && txt.charAt(txt.length-1) === "'") || (txt.charAt(0) === '"' && txt.charAt(txt.length-1) === '"')){
            const str = txt.substring(1)
            code = str.substring(0,str.length-1)
            return `'${code}'`
          } else if(txt.charAt(0) === "(" && txt.charAt(txt.length-1) === ")"){
            return `${code}`
          }else{
            return `'${code}'`
          }
        } else {
          if(/[\u4E00-\u9FA5]+/g.test(txt)){
            const code = txt.split('').map(char => {
              const code = char.charCodeAt(0).toString(16).toUpperCase();
              return '\\u' + code.padStart(4, '0');
            }).join('');
           return `"${code}"`
          } else {
            const code = `'${txt}'`
            return code
          }
        }
      },
      forceString: (txt, args) => {
        if((txt.charAt(0) === '"' && txt.charAt(txt.length-1) === '"') || (txt.charAt(0) === "'" && txt.charAt(txt.length-1) === "'")){
          return txt;
        }else{
          return `"${txt}"`
        }
      }
    }
  }